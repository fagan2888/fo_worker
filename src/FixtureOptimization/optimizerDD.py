#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Created on Thu Jun  2 11:33:51 2016

@author: kenneth.l.sylvain
"""

from pulp import *
import numpy as np
import pandas as pd
import datetime as dt


def optimizeDD(jobName, increment, dataMunged, salesPen):
    """
    Run an LP-based optimization

    Side-effects:
        - creates file: Fixture_Optimization.lp (constraints)
        - creates file: solvedout.csv <= to be inserted into db
        - creates file: solvedout.text

    Synopsis:
        I just wrapped the script from Ken in a callable - DCE
    """
    dataMunged.to_csv('DrillDownMunged.csv',sep=",")
    def roundValue(cVal, increment):
        if np.mod(round(cVal, 3), increment) > increment / 2:
            cVal = round(cVal, 3) + (increment - (np.mod(round(cVal, 3), increment)))
        else:
            cVal = round(cVal, 3) - np.mod(round(cVal, 3), increment)
        return cVal

    Stores = dataMunged['Store'].unique().tolist()
    Categories = dataMunged['Category'].unique().tolist()
    Tiers = dataMunged['Tier'].unique().tolist()
    Climates = dataMunged['Climate'].unique().tolist()

    dataMunged['Optimal Space'] = dataMunged['Optimal Space'].apply(lambda x: roundValue(x, increment))
    print('set up new space bounds')
    dataMunged = dataMunged.apply(lambda x: pd.to_numeric(x, errors='ignore'))
    start_time = dt.datetime.today().hour * 60 * 60 + dt.datetime.today().minute * 60 + dt.datetime.today().second
    dataMunged["Optimal Space"] = dataMunged["Optimal Space"].apply(lambda x: roundValue(x, increment))
    salesPenetration = dataMunged.pivot(index='Store', columns='Category', values='Sales Penetration')
    brandExitArtifact = dataMunged.pivot(index='Store', columns='Category', values='Exit Flag')
    opt_amt= dataMunged.pivot(index='Store', columns='Category', values='Optimal Space')

    b = .05
    bI = .05

    locSpaceToFill = dataMunged.groupby('Store')['New Space'].agg(np.mean)
    def adjustForTwoIncr(row, bound, increment):
        """
        Returns a vector with the maximum percent of the original total store space between two increment sizes and 10 percent of the store space
        :param row: Individual row of Total Space Available in Store
        :param bound: Percent Bounding for Balance Back
        :param increment: Increment Size Determined by the User in the UI
        :return: Returns an adjusted vector of percentages by which individual store space should be held
        """
        return max(bound, (2 * increment) / row)
    locBalBackBoundAdj = locSpaceToFill.apply(lambda row: adjustForTwoIncr(row, bI, increment))

    print("HEY I'M IN THE OPTIMIZATION!!!!!!!")
    ###############################################################################################
    # Reading in of Files & Variable Set Up|| Will be changed upon adoption into tool
    ###############################################################################################

    ##########################################################################################
    ##################Vector Creation ||May be moved to another module/ program in the future
    ##########################################################################################
    # opt_amt.index=opt_amt.index.values.astype(int)
    # Stores = opt_amt.index.tolist()
    # Setting up the Selected Tier Combinations -- Need to redo if not getting or creating data for all possible levels
    # Categories = opt_amt.columns.values
    print('creating levels')
    minLevel = dataMunged['Optimal Space'].min()
    maxLevel = dataMunged['Optimal Space'].max()
    Levels = list(np.arange(minLevel, maxLevel + increment, increment))
    if 0.0 not in Levels:
        Levels.insert(0, 0.0)
    print("created levels")

    # Adjust location balance back tolerance limit so that it's at least 2 increments
    # def adjustForTwoIncr(row,bound,increment):
    #     return max(bound,(2*increment)/row)

    # Create a Vectors & Arrays of required variables
    # Calculate Total fixtures(TotFixt) per store by summing up the individual fixture counts
    W = opt_amt.sum(axis=1).sum(axis=0)

    print('Balance Back Vector')

    ct = LpVariable.dicts('CT', (Tiers, Climates, Categories, Levels), 0, upBound=1, cat='Binary')
    st = LpVariable.dicts('ST', (Stores, Categories, Levels), 0, upBound=1, cat='Binary')
    print('tiers created')

    NewOptim = LpProblem(jobName, LpMinimize)  # Define Optimization Problem/

    print('Brand Exit Done')
    BA = np.zeros((len(Stores), len(Categories), len(Levels)))
    error = np.zeros((len(Stores), len(Categories), len(Levels)))
    for (i, Store) in enumerate(Stores):
        for (j, Category) in enumerate(Categories):
            for (k, Level) in enumerate(Levels):
                BA[i][j][k] = opt_amt[Category].iloc[i]
                error[i][j][k] = np.absolute(BA[i][j][k] - Level)

    NewOptim += lpSum(
        [(st[Store][Category][Level] * error[i][j][k]) for (i, Store) in enumerate(Stores) for (j, Category) in
         enumerate(Categories) for (k, Level) in enumerate(Levels)]), ""
    print('created objective function')
    ###############################################################################################################
    ############################################### Constraints
    ###############################################################################################################
    # Makes is to that there is only one Selected tier for each Store/ Category Combination
    for (i, Store) in enumerate(Stores):
        # TODO: Exploratory analysis on impact of balance back on financials for Enhanced
        # Store-level balance back constraint: the total space allocated to products at each location must be within the individual location balance back tolerance limit
        NewOptim += lpSum(
            [(st[Store][Category][Level]) * Level for (j, Category) in enumerate(Categories) for (k, Level) in
             enumerate(Levels)]) >= locSpaceToFill[Store] * (1 - locBalBackBoundAdj[Store])  # , "Location Balance Back Lower Limit - STR " + str(Store)
        NewOptim += lpSum(
            [(st[Store][Category][Level]) * Level for (j, Category) in enumerate(Categories) for (k, Level) in
             enumerate(Levels)]) <= locSpaceToFill[Store] * (1 + locBalBackBoundAdj[Store])  # , "Location Balance Back Upper Limit - STR " + str(Store)

    #     # One Space per Store Category
        # Makes sure that the number of fixtures, by store, does not go above or below some percentage of the total number of fixtures within the store
        for (j, Category) in enumerate(Categories):
            NewOptim += lpSum([st[Store][Category][Level] for (k, Level) in
                               enumerate(Levels)]) == 1  # , "One_Level_per_Store-Category_Combination"
    print('finished first block of constraints')

    for (c, Climate) in enumerate(Climates):
        for (t, Tier) in enumerate(Tiers):
            for (j, Category) in enumerate(Categories):
                NewOptim += lpSum([ct[Tier][Climate][Category][Level] for (k, Level) in enumerate(Levels)]) == 1
                # Relationship between Selected Tiers & Created Tiers
                # Verify that we still cannot use a constraint if not using a sum - Look to improve efficiency
                for (k, Level) in enumerate(Levels):
                    NewOptim += lpSum([st[Store][Category][Level] for (i, Store) in enumerate(Stores)]) / len(Stores) <= \
                                ct[Tier][Climate][Category][Level]  # , "Relationship between ct & st"
    print('finished the second block of constraints')

    # Global Balance Back
    NewOptim += lpSum(
        [st[Store][Category][Level] * Level for (i, Store) in enumerate(Stores) for (j, Category) in
         enumerate(Categories) for
         (k, Level) in enumerate(Levels)]) >= W * (1 - b)
    NewOptim += lpSum(
        [st[Store][Category][Level] * Level for (i, Store) in enumerate(Stores) for (j, Category) in
         enumerate(Categories) for
         (k, Level) in enumerate(Levels)]) <= W * (1 + b)
    # NewOptim.writeLP("Fixture_Optimization.lp")
    # LpSolverDefault.msg = 1
    print("The problem has been formulated")

    # Solving the Problem
    # NewOptim.writeLP("Fixture_Optimization.lp")
    # NewOptim.writeMPS(str(jobName)+".mps")
    # NewOptim.solve(pulp.GUROBI(mip=True, msg=True, MIPgap=.01))
    try:
        NewOptim.solve(pulp.GUROBI(mip=True, msg=True, MIPgap=.01, LogFile="/tmp/gurobi.log"))

    except Exception as e:
        print(e)

    # #Debugging
    print("#####################################################################")
    print(LpStatus[NewOptim.status])
    print("#####################################################################")
    # # Debugging
    # NegativeCount = 0
    # LowCount = 0
    # TrueCount = 0
    # OneCount = 0
    # for (i, Store) in enumerate(Stores):
    #     for (j, Category) in enumerate(Categories):
    #         for (k, Level) in enumerate(Levels):
    #             if value(st[Store][Category][Level]) == 1:
    #                 # print(st[Store][Category][Level]) #These values should only be a one or a zero
    #                 OneCount += 1
    #             elif value(st[Store][Category][Level]) > 0:
    #                 # print(st[Store][Category][Level],"Value is: ",value(st[Store][Category][Level])) #These values should only be a one or a zero
    #                 TrueCount += 1
    #             elif value(st[Store][Category][Level]) == 0:
    #                 # print(value(st[Store][Category][Level])) #These values should only be a one or a zero
    #                 LowCount += 1
    #             elif value(st[Store][Category][Level]) < 0:
    #                 # print(st[Store][Category][Level],"Value is: ",value(st[Store][Category][Level])) #These values should only be a one or a zero
    #                 NegativeCount += 1
    # if tierCounts is not None:
    #     ctNegativeCount = 0
    #     ctLowCount = 0
    #     ctTrueCount = 0
    #     ctOneCount = 0
    #
    #     for (j, Category) in enumerate(Categories):
    #         for (k, Level) in enumerate(Levels):
    #             if value(ct[Category][Level]) == 1:
    #                 # print(value(ct[Store][Category][Level])) #These values should only be a one or a zero
    #                 ctOneCount += 1
    #             elif value(ct[Category][Level]) > 0:
    #                 # print(ct[Store][Category][Level],"Value is: ",value(st[Store][Category][Level])) #These values should only be a one or a zero
    #                 ctTrueCount += 1
    #             elif value(ct[Category][Level]) == 0:
    #                 # print(value(ct[Category][Level])) #These values should only be a one or a zero
    #                 ctLowCount += 1
    #             elif value(ct[Category][Level]) < 0:
    #                 # print(ct[Category][Level],"Value is: ",value(st[Store][Category][Level])) #These values should only be a one or a zero
    #                 ctNegativeCount += 1
    #
    # print("Status:", LpStatus[NewOptim.status])
    # print("---------------------------------------------------")
    # print("For Selected Tiers")
    # print("Number of Negatives Count is: ", NegativeCount)
    # print("Number of Zeroes Count is: ", LowCount)
    # print("Number Above 0 and Below 1 Count is: ", TrueCount)
    # print("Number of Selected Tiers: ", OneCount)
    # print("---------------------------------------------------")
    # if tierCounts is not None:
    #     print("For Created Tiers")
    #     print("Number of Negatives Count is: ", ctNegativeCount)
    #     print("Number of Zeroes Count is: ", ctLowCount)
    #     print("Number Above 0 and Below 1 Count is: ", ctTrueCount)
    #     print("Number of Created Tiers: ", ctOneCount)
    #     print("Creating Outputs")
    if LpStatus[NewOptim.status] == 'Optimal':
        print('Found an optimal solution')
        Results = pd.DataFrame(index=Stores, columns=Categories)
        for (i, Store) in enumerate(Stores):
            for (j, Category) in enumerate(Categories):
                for (k, Level) in enumerate(Levels):
                    if value(st[Store][Category][Level]) == 1:
                        Results[Category][Store] = Level
        Results.reset_index(inplace=True)
        Results.columns.values[0] = 'Store'
        Results = pd.melt(Results.reset_index(), id_vars=['Store'], var_name='Category', value_name='Result Space')
        Results = Results.apply(lambda x: pd.to_numeric(x, errors='ignore'))
        dataMunged = pd.merge(dataMunged, Results, on=['Store', 'Category'])
        return (LpStatus[NewOptim.status], dataMunged, value(NewOptim.objective))  # (longOutput)#,wideOutput)
    else:
        dataMunged['Result Space'] = 0
        return (LpStatus[NewOptim.status], dataMunged, 0)

# if __name__ == '__main__':
#     df = pd.DataFrame(np.random.randn(10, 5), columns=['a', 'b', 'c', 'd', 'e'])
#     create_output_artifact_from_dataframe(df, filename='hello.csv')
