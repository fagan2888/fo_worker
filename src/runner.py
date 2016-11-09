#!/usr/bin/env python
# -*- coding: utf-8 -*-


import datetime as dt
from pulp import *
import config as env
import json
import gridfs
import pandas as pd
import pika
from bson.objectid import ObjectId
from pymongo import MongoClient
import config
from FixtureOptimization.CurveFitting import curveFittingBS
from FixtureOptimization.ksMerging import ksMerge
from FixtureOptimization.preoptimizerEnh import preoptimizeEnh
from FixtureOptimization.optimizerR5 import optimize
from FixtureOptimization.optimizer2 import optimize2
from FixtureOptimization.outputFunctions import createLong, createWide, createDrillDownSummary, createTieredSummary, outputValidation
from pika import BlockingConnection, ConnectionParameters
from FixtureOptimization.SingleStoreOptimization import optimizeSingleStore
import logging
import traceback

# from TierKey import tierKeyCreate
# from TierOptim import tierDef

#
# ENV VARS
#

MONGO_HOST = env.MONGO_HOST
MONGO_PORT = env.MONGO_PORT
MONGO_NAME = env.MONGO_NAME

#
# MODULE CONSTANTS
#

RMQ_QUEUE_SINK = 'notify_queue'

#
# LOGGING
#



def run(body):
    # import pdb; pdb.set_trace()
    db = MongoClient(host=MONGO_HOST,
                     port=MONGO_PORT)[MONGO_NAME]
    fs = gridfs.GridFS(db)
    
    # mq_conn = BlockingConnection(ConnectionParameters(host=RMQ_HOST,
    #                                                   port=RMQ_PORT))
    # ch = mq_conn.channel()
    # ch.queue_declare(queue=RMQ_QUEUE_SINK, durable=True)

    def create_output_artifact_from_dataframe(dataframe, *args, **kwargs):
        """
        Returns the bson.objectid.ObjectId of the resulting GridFS artifact

        """
        return fs.put(dataframe.to_csv(index=False).encode(), **kwargs)

    def fetch_artifact(artifact_id):
        file = fs.get(ObjectId(artifact_id))
        file = pd.read_csv(file, header=0)
        return file

    msg = json.loads(body.decode('utf-8'))
    # Find job to check status of job
    job = db.jobs.find_one({'_id': ObjectId(msg['_id'])})
    try:
        job_id = job['_id']
    except TypeError:
        print('Job Not Found')
        return False

    # current_user = job['userId']
    # job_status = job['status']
    worker_start_time = dt.datetime.utcnow()
    db.jobs.update_one(
        {'_id': job['_id']},
        {
            "$set": {
                "status": "running",
                'worker_start_time': worker_start_time
            }
        }
    )
    # res = dict(user_id=job['userId'], status='running')
    # ch.basic_publish(exchange='',
    #          routing_key=RMQ_QUEUE_SINK,
    #          body=json.dumps(res))

    def fetchTransactions(artifact_id):
        file = fs.get(ObjectId(artifact_id))
        file = pd.read_csv(file, header=None)
        return file

    def fetchSpace(artifact_id):
        file = fs.get(ObjectId(artifact_id))
        file = pd.read_csv(file, header=0, dtype={'Store': object}, skiprows=[1])
        return file

    def fetchExit(artifact_id):
        file = fs.get(ObjectId(artifact_id))
        file = pd.read_csv(file, header=0, skiprows=[1])
        return file

    # Stores = msg['salesStores']
    # Categories = msg['salesCategories']

    # logging.info('beginning of ' + msg['meta']['name'])

    print("#####################################################################")
    print('beginning of ' + msg['meta']['name'] + 'date of ' + dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("#####################################################################")


    try:
        futureSpace = fetchSpace(msg["artifacts"]["futureSpaceId"])
        print("Future Space was Uploaded")
    except:
        futureSpace = None
        print("Future Space was not Uploaded")
    try:
        brandExitArtifact = fetchExit(msg["artifacts"]["brandExitArtifactId"])
        print("Brand Exit was Uploaded")
    except:
        print("Brand Exit was not Uploaded")
        brandExitArtifact = None
    if msg['jobType'] == 'unconstrained':
        msg['tierCounts'] = None

    dataMerged = ksMerge(msg['meta']['name'],msg['jobType'], fetchTransactions(msg["artifacts"]["salesArtifactId"]),
                            fetchSpace(msg["artifacts"]["spaceArtifactId"]),
                            brandExitArtifact, futureSpace)
    print('finished data merging')
    preOpt = preoptimizeEnh(optimizationType=msg['optimizationType'], dataMunged=dataMerged[1],
                            mAdjustment=float(msg["metricAdjustment"]),
                            salesPenThreshold=float(msg["salesPenetrationThreshold"]),
                            optimizedMetrics=msg["optimizedMetrics"], increment=msg["increment"])
    print('finished preoptimize')
    if msg['optimizationType'] == 'traditional':
        print('going to the optimization')
        optimRes = optimize(jobName=msg['meta']['name'], Stores=msg['salesStores'], Categories=msg['salesCategories'],
                            spaceBound=msg['spaceBounds'], increment=msg['increment'], dataMunged=preOpt,
                            tierCounts=msg['tierCounts'])
        cfbsArtifact=[None,None]
    else:
        cfbsArtifact = curveFittingBS(dataMerged[0], msg['spaceBounds'], msg['increment'],
                                    msg['storeCategoryBounds'],
                                    float(msg["salesPenetrationThreshold"]), msg['jobType'],
                                    msg['optimizationType'])
        print('finished curve fitting')
        cfbsOptimal = optimizeSingleStore(cfbsArtifact[0].set_index(['Store', 'Category']), msg['increment'],
                                        msg['optimizedMetrics'])
        print('finished single store')
        # if msg['jobtype'] == 'tiered':
        print('original optimization')
        optimRes = optimize2(methodology=msg['optimizationType'], jobName=msg['meta']['name'],
                             Stores=msg['salesStores'], Categories=msg['salesCategories'],
                             increment=msg['increment'], weights=msg['optimizedMetrics'], cfbsOutput=cfbsOptimal[1],
                             preOpt=preOpt, salesPen=msg['salesPenetrationThreshold'], tierCounts=msg['tierCounts'])

            # else:
        #     optimRes = optimizeUncon(methodology=msg['optimizationType'], jobName=msg['meta']['name'],
        #                         Stores=msg['salesStores'], Categories=msg['salesCategories'],
        #                         increment=msg['increment'], weights=msg['optimizedMetrics'], cfbsOutput=cfbsOptimal[1],
        #                         preOpt=preOpt, salesPen=msg['salesPenetrationThreshold'])
    print('we just did the optimization')
    print('New optimization completed')


    # Call functions to create output information
    print('Out of the optimization')
    longOutput = createLong(msg['jobType'],msg['optimizationType'], optimRes[1])
    print('Created Long Output')
    wideID = str(create_output_artifact_from_dataframe(createWide(longOutput, msg['jobType'], msg['optimizationType'])))
    print('Created Wide Output')

    if cfbsArtifact[1] is not None:
        longID = str(create_output_artifact_from_dataframe(longOutput))
        analyticsID = str(create_output_artifact_from_dataframe(cfbsArtifact[1]))
        print('Created analytics ID')
    else:
        longID = str(create_output_artifact_from_dataframe(
            longOutput[['Store', 'Category', 'Climate', 'VSG', 'Sales Penetration', 'Result Space', 'Current Space', 'Optimal Space']]))
        analyticsID=None
        print('Set analytics ID to None')
    
    statusID = optimRes[0]
    print(statusID)
    print('Set the Status')
    
    if msg['jobType'] == "tiered" or 'unconstrained':
        summaryID = str(create_output_artifact_from_dataframe(createTieredSummary(longOutput)))
    else:  # since type == "Drill Down"
        summaryID = str(create_output_artifact_from_dataframe(createDrillDownSummary(longOutput)))
    print('Set the summary IDs')

    try:
        invalids = outputValidation(df=longOutput, jobType=msg['jobType'], tierCounts=msg['tierCounts'], increment=msg['increment'])
    except Exception as e:
        print(e)
        traceback.print_exc(e)
        print(traceback.print_stack())
    print('set the invalids')

    end_time = dt.datetime.utcnow()
    print('created the end time')

    print("Adding end time and output ids")
    db.jobs.find_one_and_update(
        {'_id': job_id},
        {
            "$set": {
                'optimization_end_time': end_time,
                "status": statusID,
                "objectiveValue": optimRes[2],
                "artifactResults": {
                    'long_table':longID,
                    'wide_table':wideID,
                    'summary_report': summaryID,
                    'analytic_data': analyticsID
                },
                "outputErrors":{
                    'invalidValues': invalids[0],
                    'invalidTierCounts': invalids[1],
                    'invalidBrandExit': invalids[2],
                    'invalidSalesPenetration': invalids[3],
                    'invalidBalanceBack': invalids[4]
                }
            }
        }
    )

    # logging.info('end of ' + msg['meta']['name'])

    print("#####################################################################")
    print(dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    print("#####################################################################")

    print("Job complete")

if __name__ == '__main__':
    # LOGGER.debug('hello from {}'.format(__name__))
    logger.debug('hello from {}'.format(__name__))
