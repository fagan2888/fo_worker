# -*- coding: utf-8 -*-
"""
Created on Thu Jun 30 09:55:06 2016

@author: kenneth.l.sylvain
"""
import numpy as np
import pandas as pd


transaction_data = pd.read_csv("C:\\Users\\kenneth.l.sylvain\\Documents\\Kohls\\Fixture Optimization\\Sprint 1\\transactions_data.csv",header=0).set_index("Store #")
data=transaction_data
fixture_data = pd.read_csv("C:\\Users\\kenneth.l.sylvain\\Documents\\Kohls\\Fixture Optimization\\Sprint 1\\fixture_data.csv",header=0).set_index("Store")
bfc =fixture_data[[ *np.arange(len(fixture_data.columns))[2::2] ]].drop(fixture_data.index[[0]]).convert_objects(convert_numeric=True)

# Read in Optimized Metrics as a JSON object

# Convert Optimized Metrics to a Dictionary


####################

# import os
''''
class SampleFile(object):

    src_path = os.path.dirname(__file__)
    test_files_path = os.path.join(os.path.dirname(src_path),
                                   'test/test_optimizer_files')

    @classmethod
    def get(cls, filename):
        return os.path.join(cls.test_files_path, filename)

'''
def calcPen(metric):
    return metric.div(metric.sum(axis=1),axis='index')
    
def getColumns(df):
    return df[[ *np.arange(len(df.columns))[0::8] ]].drop(df.index[[0]]).convert_objects(convert_numeric=True).columns

# def calcPen(metric,master_columns):
#     metric.columns = master_columns
#     return metric.div(metric.sum(axis=1),axis='index')

def spreadCalc(sales,boh,receipt,master_columns,salesPenetrationThreshold):
     # storing input sales and inventory data in separate 2D arrays
	 # finding sales penetration, GAFS and spread for each brand in given stores
	 # calculate adjusted penetration
     #Not necessary -- sales.columns = master_columns
     print(str(boh.columns))
     #print(str(master_columns))
     boh.columns = master_columns
     receipt.columns = master_columns
     inv=boh + receipt
     return calcPen(sales) + ((calcPen(sales) - calcPen(inv)) * float(salesPenetrationThreshold))

def spCalc(metric,master_columns):
    # storing input sales data in an array
    # finding sales penetration for each brand in given stores
    # calculate adjusted penetration
    metric.columns = master_columns
    return calcPen(metric)

def metric_per_metric(metric1,metric2,salesPenetrationThreshold,master_columns):
    # storing input sales data in an array
		# finding penetration for each brand in given stores
		# calculate adjusted penetration
    metric1.columns = master_columns
    metric2.columns = master_columns
    return calcPen(metric1) + ((calcPen(metric1) - calcPen(metric2)) * float(salesPenetrationThreshold))


def invTurn_Calc(sold_units,boh_units,receipts_units,master_columns):
    sold_units.columns = master_columns
    boh_units.columns = master_columns
    receipts_units.columns = master_columns
    calcPen(sold_units)
    calcPen(boh_units+receipts_units)
    inv_turn = calcPen(sold_units).div(calcPen(boh_units+receipts_units),axis='index')
    inv_turn[np.isnan(inv_turn)] = 0
    inv_turn[np.isinf(inv_turn)] = 0
    return calcPen(inv_turn)
    
def roundArray(array,increment):
    rounded=np.copy(array)
    for i in range(len(array)):
        for j in range(len(list(array[0,:]))):
            if np.mod(np.around(array[i][j], 0), increment) > increment/2:
                rounded[i][j] = np.around(array[i][j], 0) + (increment-(np.mod(np.around(array[i][j], 0), increment)))
            else:         
                rounded[i][j] = np.around(array[i][j], 0) - np.mod(np.around(array[i][j], 0), increment)
    return rounded

def roundDF(array,increment):
    rounded = array.copy(True)
    for i in array.index:
        for j in array.columns:
            if np.mod(np.around(array[j].loc[i], 3), increment) > increment/2:
                rounded[j].loc[i] = np.around(array[j].loc[i], 3) + (increment-(np.mod(np.around(array[j].loc[i], 3), increment)))
            else:         
                rounded[j].loc[i] = np.around(array[j].loc[i], 3) - np.mod(np.around(array[j].loc[i], 3), increment)
    return rounded

def preoptimize(fixture_data,data,metricAdjustment,salesPenetrationThreshold,optimizedMetrics,increment):
 
    # fixture_data.index  
    bfc = fixture_data[[ *np.arange(len(fixture_data.columns))[2::2] ]].drop(fixture_data.index[[0]]).convert_objects(convert_numeric=True)      
    sales = data[[ *np.arange(len(data.columns))[0::8] ]].drop(data.index[[0]]).convert_objects(convert_numeric=True)
    boh = data[[ *np.arange(len(data.columns))[1::8] ]].drop(data.index[[0]]).convert_objects(convert_numeric=True)
    receipt = data[[ *np.arange(len(data.columns))[2::8] ]].drop(data.index[[0]]).convert_objects(convert_numeric=True)
    sold_units = data[[ *np.arange(len(data.columns))[3::8] ]].drop(data.index[[0]]).convert_objects(convert_numeric=True)
    boh_units = data[[ *np.arange(len(data.columns))[4::8] ]].drop(data.index[[0]]).convert_objects(convert_numeric=True)
    receipts_units = data[[ *np.arange(len(data.columns))[5::8] ]].drop(data.index[[0]]).convert_objects(convert_numeric=True)
    profit = data[[ *np.arange(len(data.columns))[6::8] ]].drop(data.index[[0]]).convert_objects(convert_numeric=True)
    gm_perc = data[[ *np.arange(len(data.columns))[7::8] ]].drop(data.index[[0]]).convert_objects(convert_numeric=True)

    adj_p = optimizedMetrics['spread']*spreadCalc(sales,boh,receipt,getColumns(data),salesPenetrationThreshold) + optimizedMetrics['salesPenetration']*spCalc(sales,getColumns(data)) + optimizedMetrics['salesPerUnitSpace']*metric_per_metric(sales,bfc,salesPenetrationThreshold,getColumns(data)) + optimizedMetrics['grossMargin']*spCalc(gm_perc,getColumns(data)) +optimizedMetrics['marginPerUnitSpace']*metric_per_metric(profit,bfc,salesPenetrationThreshold,getColumns(data)) + optimizedMetrics['inventoryTurns']*invTurn_Calc(sold_units,boh_units,receipts_units,getColumns(data))
    


    adj_p[np.isnan(adj_p)] = 0
    for i in adj_p.index:
        for j in adj_p.columns:
            if adj_p[j].loc[i] < metricAdjustment:
                adj_p[j].loc[i] = 0
    adj_p=calcPen(adj_p)
    adj_p[np.isnan(adj_p)] = 0
        
    opt_amt = roundDF(adj_p.multiply(bfc.sum(axis=1),axis='index'),increment)    
    #return adj_p
    return opt_amt


#For Testing 
metricAdjustment=0
salesPenetrationThreshold=0
metric=6
increment=.25
adj_p = preoptimize(transaction_data, bfc,metricAdjustment,salesPenetrationThreshold,metric,increment)
#adj_p.head()

#opt_amt=adj_p.multiply(bfc.sum(axis=1),axis='index').as_matrix()