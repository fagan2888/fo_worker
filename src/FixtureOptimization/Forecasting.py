from scipy.special import erf
import pandas as pd
import math as math
import json
import pika
import time

# a=forecast_function(p_f)

def forecastFunction(p_fcst,spaceCol):
#Create two new columns to store generated values

    p_fcst["Estimated_Sales"] = 0
    p_fcst["Estimated_Units"] = 0
    p_fcst["Estimated_Profit"] = 0
    
    #Generate new values
    if p_fcst[spaceCol].any()<p_fcst["Scaled_BP_Sales"].any():
        p_fcst["Estimated_Sales"] = p_fcst[spaceCol]*p_fcst["Scaled_Alpha_Sales"]*(erf((p_fcst["Scaled_BP_Sales"]-p_fcst["Scaled_Shift_Sales"])/(math.sqrt(2)*p_fcst["Scaled_Beta_Sales"])))/p_fcst["Scaled_BP_Sales"]
    else: 
        p_fcst["Estimated_Sales"] = p_fcst["Scaled_Alpha_Sales"]*erf((p_fcst[spaceCol]-p_fcst["Scaled_Shift_Sales"])/(math.sqrt(2)*p_fcst["Scaled_Beta_Sales"]))
    
    if p_fcst[spaceCol].any()<p_fcst["Scaled_BP_Units"].any():
        p_fcst["Estimated_Units"] = p_fcst[spaceCol]*p_fcst["Scaled_Alpha_Units"]*(erf((p_fcst["Scaled_BP_Units"]-p_fcst["Scaled_Shift_Units"])/(math.sqrt(2)*p_fcst["Scaled_Beta_Units"])))/p_fcst["Scaled_BP_Units"]
    else:
        p_fcst["Estimated_Units"] = p_fcst["Scaled_Alpha_Units"]*erf((p_fcst[spaceCol]-p_fcst["Scaled_Shift_Units"])/(math.sqrt(2)*p_fcst["Scaled_Beta_Units"]))
    
    
    if p_fcst[spaceCol].any()<p_fcst["Scaled_BP_Profit"].any():
        p_fcst["Estimated_Profit"] = p_fcst[spaceCol]*p_fcst["Scaled_Alpha_Profit"]*(erf((p_fcst["Scaled_BP_Profit"]-p_fcst["Scaled_Shift_Profit"])/(math.sqrt(2)*p_fcst["Scaled_Beta_Profit"])))/p_fcst["Scaled_BP_Profit"]
    else:
        p_fcst["Estimated_Profit"] = p_fcst["Scaled_Alpha_Profit"]*erf((p_fcst[spaceCol]-p_fcst["Scaled_Shift_Profit"])/(math.sqrt(2)*p_fcst["Scaled_Beta_Profit"]))
    
    p_fcst_out=p_fcst[["Store","Climate","VSG","Product","Space","Sales","Units","Profit",str(spaceCol),"Estimated_Sales","Estimated_Profit","Estimated_Units","Lower_Limit","Upper_Limit"]]
    
    p_fcst_out.set_index(["Store","Product","Space"])
    return(p_fcst_out)

# spaceCol='Recommended_Space'