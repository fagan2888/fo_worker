# Accenture & Kohl's Proprietary and Confidential Information.
# This code contains Accenture Materials; the code and the concepts used in it are subject to the 
# Top Down Macro Space Optimization Approach agreement between Accenture & Kohl's.  

# rm(list=ls())  #Clear historical data from R server

# curr_prod_name <- "TEST"
# setwd(paste0("C:\\Users\\alison.stern\\Documents\\Kohls\\FO Enhancements\\R Code\\Testing 09.29.2016\\",curr_prod_name))
#setwd('/Users/kenneth.l.sylvain/Documents/SingleStore')
#mydir<-('/Users/kenneth.l.sylvain/Documents/SingleStore')

#library(tidyr)  #For data manipulation
#library(gdata)

# Curve Fitting and Bound Setting Function
curvefitting_boundsetting<-function(master,bound_input,increment,pct_chg_limit,sls_pen_thresh,jobType,methodology){
  library(nloptr) #For running optimization to find unscaled coefficients
  library(pracma) #For error function
#  methodology='tiered'
  # BEGIN curve-fitting
  print(jobType)
  print(methodology)
  print(jobType=='tiered')
  print(methodology=='enhanced')
  #	Minimal Store-Category History Filters
  space_filter <- 0.1
  Sales_filter <- 20
  Profit_filter <- 5
  Units_filter <- 5
  
  #	Minimal Category-Climate Group History Filters
  strcount_filter <- 100
  avgSales_filter <- 200
  avgProfit_filter <- 50
  avgUnits_filter <- 50

  get_mode <- function(x) {
    ux <- unique(x)
    ux[which.max(tabulate(match(x, ux)))]
  }
  
  get_mode_frequency <- function(x) {
    ux <- unique(x)
    max(tabulate(match(x, ux)))
  }
  
  growth_factor <- 0.1

  # Rename column titles where column title contains blanks and drop irrelevant columns
  names(master)[names(master) == "Current.Space"] <- "Space"
  names(master)[names(master) == "Sales.."] <- "Sales"
  names(master)[names(master) == "Profit.."] <- "Profit"
  names(master)[names(master) == "Sales.Units"] <- "Units"
  names(master)[names(master) == "New.Space"] <- "Space_to_Fill"
  names(master)[names(master) == "Exit.Flag"] <- "Exit_Flag"
  master <- master[c("Store", "Climate", "Category", "Space", "Sales", "Profit", "Units", "Exit_Flag", "Space_to_Fill")]

  print('made it past the column names')
  # Assign Climate Groups
  master$Climate_Group <- as.character(master$Climate)
  if(jobType == "tiered"){
    master$Climate_Group <- "NA"
  } else {
    master$Climate_Group <- ifelse((master$Climate_Group == "HOT" | master$Climate_Group == "SUPER HOT"), "HOT & SH", master$Climate_Group)
  }
  master$Category_CG <- paste0(master$Category,"-",master$Climate_Group)

  print('assigned climate groups')
  # Initialize data frame to hold unscaled curve information (analytics reference data)
  ref <- structure(list(Category_SG=character()), class = "data.frame")

  k <- 0
  firstmetric <- TRUE
  
#  for(target in c("Sales","Profit","Units")){
  for(target in c("Sales")){
    # Business Area Productivity Calculation
    master[,paste0("BA_Prod_",target)] <- NA
    for(j in 1:nrow(master)){
      master[,paste0("BA_Prod_",target)][j] <- sum(master[,target][which(master$Store %in% master$Store[j])])/sum(master$Space[which(master$Store %in% master$Store[j])])
    }

    #	Flag Store-Categories with Minimal History
    master[,paste0("Str_Cat_Flag_",target)] <- 0
    master[,paste0("Str_Cat_Flag_",target)] <- ifelse((master$Space < space_filter | master[,target] < get(paste0(target,"_filter"))), 1, 0)

    #	Flag Category-Climate Groups with Minimal History
    eligiblePrelim<-master[which(master[,paste0("Str_Cat_Flag_",target)] == 0),]
    targetStats = do.call(data.frame, aggregate(x = eligiblePrelim[target], by = eligiblePrelim["Category_CG"], FUN = function(x) c(Average = mean(x), Str_Count = length(x))))
    remove(eligiblePrelim)
    targetStats[,paste0("Cat_CG_Flag_",target)] <- 0
     targetStats[,paste0("Cat_CG_Flag_",target)] <- ifelse((targetStats[,paste0(target,".Str_Count")] < strcount_filter | targetStats[,paste0(target,".Average")] < get(paste0("avg",target,"_filter"))), 1, 0)
    master <- merge(master,targetStats[ , c("Category_CG", paste0("Cat_CG_Flag_",target))],by="Category_CG",all.x=TRUE)
    master[,paste0("Cat_CG_Flag_",target)][is.na(master[,paste0("Cat_CG_Flag_",target)])] <- 0

    # Select the data eligible for curve-fitting, which passed all filters
    eligible <- master[which(master[,paste0("Str_Cat_Flag_",target)] == 0 & master[,paste0("Cat_CG_Flag_",target)] == 0),]
    eligible <- eligible[c("Store","Category", "Category_CG","Climate_Group",paste0("BA_Prod_",target),"Space",target)]
    
    # Assign Productivity Groups
    prodStats <- do.call(data.frame, 
                         aggregate(x = eligible[,paste0("BA_Prod_",target)], 
                                   by = eligible["Category_CG"], 
                                   FUN = function(x) c(
                                     Str_Count = length(x), 
                                     q1 = quantile(x, probs = 0.25), 
                                     q2 = quantile(x, probs = 0.5), 
                                     q3 = quantile(x, probs = 0.75))))
    rownames(prodStats) <- prodStats$Category_CG
    eligible[,paste0("BA_Prod_Group_",target)] <- NA
    for(q in (1:nrow(eligible))){
      currCatCG <- eligible[q,"Category_CG"]
      if(prodStats[currCatCG,"x.Str_Count"] >= 600){
        eligible[q,paste0("BA_Prod_Group_",target)] <- 
          ifelse(eligible[q,paste0("BA_Prod_",target)]<prodStats[currCatCG,"x.q1.25."],
                 "Low",
                 ifelse(eligible[q,paste0("BA_Prod_",target)]>prodStats[currCatCG,"x.q3.75."],
                        "High",
                        "Medium"))
      } else if (prodStats[currCatCG,"x.Str_Count"] >= 300){
        eligible[q,paste0("BA_Prod_Group_",target)] <- 
          ifelse(eligible[q,paste0("BA_Prod_",target)]<prodStats[currCatCG,"x.q2.50."],
                 "Low",
                 "High")
      } else {
        eligible[q,paste0("BA_Prod_Group_",target)] <- "NA"
      }
    }
    print('assigned productivity groups')

    # Assign Store Groups
    eligible[paste0("Store_Group_",target)] <- "NA"
    if(jobType == "tiered"){
      eligible[paste0("Store_Group_",target)] <- eligible[,paste0("BA_Prod_Group_",target)]
    } else {
      eligible[paste0("Store_Group_",target)] <- paste0(eligible$Climate_Group,":",eligible[,paste0("BA_Prod_Group_",target)])
    }
    eligible$Category_SG <- paste0(eligible$Category,"-",eligible[,paste0("Store_Group_",target)])
    print('assigned Store Groups')

    # Loop through each category-store group to generate unscaled coefficients
    cat_sg_list <- unique(eligible$Category_SG)
    first_curve <- TRUE
    for (j in 1:nrow(data.frame(cat_sg_list))){

      k = k + 1
      
      cfdata <- eligible[which(eligible$Category_SG %in% cat_sg_list[j]),]
      ref[k,"Category_SG"] <- cat_sg_list[j]
      ref[k,"Category"] <- cfdata[1,"Category"]
      ref[k,"Store_Group"] <- cfdata[1,paste0("Store_Group_",target)]
      ref[k,"Metric"] <- target
      
      if(length(unique(cfdata$Space)) == 1){
        ref[k,"Correlation"] <- 0
      }else{
        ref[k,"Correlation"] <- cor(cfdata[,c(target,"Space")])[1,2]
      }

      # Handle special case of minimal space variation
      if(get_mode_frequency(cfdata$Space) > 0.95 * length(cfdata$Space) ){

        ref[k,"Special Case"] <- "Minimal Space Variation"

        ref[k,"Alpha_Seed"] <- mean(cfdata[,target]) * (1 + growth_factor)
        ref[k,"Shift_Seed"] <- 0
        spacebetaseed <- get_mode(cfdata$Space)
        targetbetaseed <- spacebetaseed * (sum(cfdata[,target])/sum(cfdata$Space))
        ref[k,"Beta_Seed"] <- -(spacebetaseed-ref[k,"Shift_Seed"])/qnorm((1-targetbetaseed/ref[k,"Alpha_Seed"])/2)
        Estimate<-c(ref[k,"Alpha_Seed"],ref[k,"Beta_Seed"],ref[k,"Shift_Seed"])
        coef<-data.frame(Estimate)
        coef<-data.frame(t(data.frame(coef)))
        colnames(coef)<-c("Alpha","Beta","Shift")

      } else {

        ref[k,"Special Case"] <- "NA"

        # Starting values for unscaled coefficients
        ref[k,"Alpha_Seed"] <- max(
          mean(cfdata[,target]) * (1 + growth_factor),
          mean(cfdata[,target][which(cfdata$Space>=quantile(cfdata$Space, .75))]))
        spacebetaseed <- mean(cfdata$Space[which(cfdata$Space<=quantile(cfdata$Space, .25))])
        targetbetaseed <- min(
          mean(cfdata[,target][which(cfdata$Space<=quantile(cfdata$Space, .25))]),
          ref[k,"Alpha_Seed"],
          spacebetaseed * (sum(cfdata[,target])/sum(cfdata$Space)))
        ref[k,"Shift_Seed"] <- 0
        ref[k,"Beta_Seed"] <- max(0,-(spacebetaseed-ref[k,"Shift_Seed"])/qnorm((1-targetbetaseed/ref[k,"Alpha_Seed"])/2))

        # Lower bounds for unscaled coefficients
        ref[k,"Alpha_LB"] <- 0
        ref[k,"Shift_LB"] <- 0
        spacebetalb <- quantile(cfdata$Space, 0.01)
        mean_target <- mean(cfdata[,target])
        targetbetalblinearprod <- spacebetalb * (sum(cfdata[,target])/sum(cfdata$Space))
        targetbetalb <- (mean_target + targetbetalblinearprod)/2
        ref[k,"Beta_LB"] <- -(spacebetalb-ref[k,"Shift_Seed"])/qnorm((1-targetbetalb/mean_target)/2)
        ref[k,"Beta_Seed"] <- max(ref[k,"Beta_Seed"],ref[k,"Beta_LB"])

        # Upper bounds for unscaled coefficients
        ref[k,"Alpha_UB"] <- quantile(cfdata[,target], 0.95)
        ref[k,"Beta_UB"] <- Inf
        ref[k,"Shift_UB"] <- ifelse(min(cfdata$Space) < 2 * max(1, increment) | ref[k,"Correlation"] <= 0.2, 0, min(cfdata$Space) - max(1, increment))

        # Define functional form
        Space <- cfdata$Space
        targetset <- cfdata[,target]
        predfun <- function(par) {
          Alpha <- par[1]
          Beta <- par[2]
          Shift <- par[3]
          rhat <- Alpha*erf((Space-Shift)/(sqrt(2)*Beta))
          r <- sum((targetset - rhat)^2)
          return(r)
        }

        # Store unscaled coefficient seed values and bounds
        x0 <- c(ref[k,"Alpha_Seed"],ref[k,"Beta_Seed"],ref[k,"Shift_Seed"])
        lower_bounds <- c(ref[k,"Alpha_LB"],ref[k,"Beta_LB"],ref[k,"Shift_LB"])
        upper_bounds <- c(ref[k,"Alpha_UB"],ref[k,"Beta_UB"],ref[k,"Shift_UB"])
        
        # Solve for unscaled coefficients using optimization function "auglag"
        model <- auglag(x0, predfun, gr=NULL, lower=lower_bounds, upper=upper_bounds, localsolver=c("MMA"))
        
        #Extract model results 
        coef <- t(data.frame(model$par))
        
      }
      
      # Finalize unscaled coefficients
      coef[,c(1,2,3)] <- round(coef[,c(1,2,3)],4)
      ref[k,"Unscaled_Alpha"] <- coef[1]
      ref[k,"Unscaled_Beta"] <- coef[2]
      ref[k,"Unscaled_Shift"] <- coef[3]
      ref[k,"Unscaled_BP"] <- ifelse(ref[k,"Unscaled_Shift"]==0,0,quantile(cfdata$Space, 0.01))
      ref[k,"Unscaled_BP_Target"] <- ref[k,"Unscaled_Alpha"]*erf((ref[k,"Unscaled_BP"]-ref[k,"Unscaled_Shift"])/(sqrt(2)*ref[k,"Unscaled_Beta"]))
      ref[k,"Unscaled_BP_Prod"] <- ref[k,"Unscaled_BP_Target"]/ref[k,"Unscaled_BP"]
      ref[k,"Critical_Point"] <- ref[k,"Unscaled_Shift"]+sqrt(2)*ref[k,"Unscaled_Beta"]*sqrt(log(sqrt(7/11)*(ref[k,"Unscaled_Alpha"]/ref[k,"Unscaled_Beta"])))
      
      # Calculate goodness-of-fit statistics
      Prediction <- ref[k,"Unscaled_Alpha"]*erf((cfdata$Space-ref[k,"Unscaled_Shift"])/(sqrt(2)*ref[k,"Unscaled_Beta"]))
      ref[k,"Quasi_R_Squared"] <- 1-sum((cfdata[,target]-Prediction)^2)/(length(cfdata[,target])*var(cfdata[,target]))  # Valid when reasonably close to linear
      ref[k,"MAPE"] <- mean(abs(Prediction-(cfdata[,target]))/(cfdata[,target])) # Mean Absolute Percentage Error

      # BEGIN store scaling calculations
      
      # Calculate the historical productivity of the store-category
      cfdata[,paste0("Productivity_",target)] <- cfdata[,target]/cfdata$Space
      
      # Calculate the expected target value based on the unscaled curve at the store-category's historical space
      cfdata[,paste0("Unscaled_Predicted_",target)] <- 
        ifelse(cfdata$Space<ref[k,"Unscaled_BP"],
               cfdata$Space*ref[k,"Unscaled_BP_Prod"],
               ref[k,"Unscaled_Alpha"]*erf((cfdata$Space-ref[k,"Unscaled_Shift"])/(sqrt(2)*ref[k,"Unscaled_Beta"])))
      
      # Determine the scaling type for use in scaling calculations
      cfdata[,paste0("Scaling_Type_",target)] <- 
        ifelse(cfdata$Space>ref[k,"Critical_Point"],
               "E", # Type E: space above where the curve has flattened out
               ifelse(cfdata[,target]>=cfdata[,paste0("Unscaled_Predicted_",target)],
                      ifelse(cfdata[,target]>=ref[k,"Unscaled_BP_Target"],
                             "A", # Type A: over-performs unscaled curve and is outside unscaled BP/BP Target rectangle 
                             "C"), # Type C: over-performs unscaled curve and is inside unscaled BP/BP Target rectangle
                      ifelse(cfdata$Space>=ref[k,"Unscaled_BP"],
                             "B", # Type B: under-performs unscaled curve and is outside unscaled BP/BP Target rectangle
                             "D"))) # Type D: under-performs unscaled curve and is inside unscaled BP/BP Target rectangle
      
      # Find the space of the data point that the scaled S curve should go through
      cfdata[,paste0("Space2Solve4_",target)] <- 
        ifelse((cfdata[,paste0("Scaling_Type_",target)]=="A" | cfdata[,paste0("Scaling_Type_",target)]=="B"),
               cfdata$Space,
               ref[k,"Unscaled_BP"])
      
      # Find the target of the data point that the scaled S curve should go through
      cfdata[,paste0(target,"2Solve4")] <- 
        ifelse((cfdata[,paste0("Scaling_Type_",target)]=="A" | cfdata[,paste0("Scaling_Type_",target)]=="B"),
               cfdata[,target],
               ref[k,"Unscaled_BP"]*cfdata[,paste0("Productivity_",target)])
      
      # Scale the alpha by the difference between store's historical target value and the unscaled expected target value
      cfdata[,paste0("Scaled_Alpha_",target)] <- 
        ref[k,"Unscaled_Alpha"]+cfdata[,target]-cfdata[,paste0("Unscaled_Predicted_",target)]
      
      # Scale the shift, keeping slope steady relative to unscaled curve unless/until break point assumption is not needed
      cfdata[,paste0("Scaled_Shift_",target)] <- 
        ifelse((cfdata[,paste0("Scaling_Type_",target)]=="A" | cfdata[,paste0("Scaling_Type_",target)]=="C"),
               pmax(0,cfdata[,paste0("Space2Solve4_",target)]+ref[k,"Unscaled_Beta"]*qnorm((1-(cfdata[,paste0(target,"2Solve4")]/cfdata[,paste0("Scaled_Alpha_",target)]))/2)),
               ref[k,"Unscaled_Shift"])

      # Scale the beta such that the final scaled S curve goes through the identified point
      cfdata[,paste0("Scaled_Beta_",target)] <- 
        ifelse(cfdata[,paste0("Scaling_Type_",target)]=="E",
               ref[k,"Unscaled_Beta"],
               (cfdata[,paste0("Scaled_Shift_",target)]-cfdata[,paste0("Space2Solve4_",target)])/(qnorm((1-(cfdata[,paste0(target,"2Solve4")]/cfdata[,paste0("Scaled_Alpha_",target)]))/2)))
      
      # Scale the break point when a linear assumption is needed
      if(ref[k,"Unscaled_BP"]==0){
       
        cfdata[,paste0("Scaled_BP_",target)] <- 0
        cfdata[,paste0(target,"_at_Scaled_BP")] <- 0
        cfdata[,paste0("Prod_at_Scaled_BP_",target)] <- 0
         
      } else{
        
        cfdata[,paste0("Scaled_BP_",target)] <- 
          ifelse(!cfdata[,paste0("Scaling_Type_",target)]=="A",
                 ref[k,"Unscaled_BP"],
                 cfdata[,paste0("Scaled_Shift_",target)]-cfdata[,paste0("Scaled_Beta_",target)]*qnorm((1-(ref[k,"Unscaled_BP_Target"]/cfdata[,paste0("Scaled_Alpha_",target)]))/2))
        
        cfdata[,paste0(target,"_at_Scaled_BP")] <- cfdata[,paste0("Scaled_Alpha_",target)]*erf((cfdata[,paste0("Scaled_BP_",target)]-cfdata[,paste0("Scaled_Shift_",target)])/(sqrt(2)*cfdata[,paste0("Scaled_Beta_",target)]))
        
        cfdata[,paste0("Prod_at_Scaled_BP_",target)] <- cfdata[,paste0(target,"_at_Scaled_BP")]/cfdata[,paste0("Scaled_BP_",target)]
      
      }
      
      # Calculate the expected target value based on the scaled curve at historical space, which equals historical target
      cfdata[,paste0("Scaled_Predicted_",target)] <- 
        ifelse(cfdata$Space<cfdata[,paste0("Scaled_BP_",target)],
               cfdata$Space*cfdata[,paste0("Prod_at_Scaled_BP_",target)],
               cfdata[,paste0("Scaled_Alpha_",target)]*erf((cfdata$Space-cfdata[,paste0("Scaled_Shift_",target)])/(sqrt(2)*cfdata[,paste0("Scaled_Beta_",target)])))
      
      # END store scaling calculations
      
      drop <- c("Category_SG",paste0("Productivity_",target),paste0("Unscaled_Predicted_",target),paste0("Scaling_Type_",target),
                paste0("Space2Solve4_",target),paste0(target,"2Solve4"),paste0(target,"_at_Scaled_BP"),
                paste0("Prod_at_Scaled_BP_",target),paste0("Scaled_Predicted_",target))
      cfdata = cfdata[,!(names(cfdata) %in% drop)]

      # Combine coefficient information for all curves within the same metric
      if(first_curve){
        eligibleScaled <- cfdata
        first_curve <- FALSE
      } else{
        eligibleScaled <- rbind(eligibleScaled,cfdata)
      }
      
    }
    print('created unscaled coefficients')

    # Merge coefficient information for each metric into the master data set
    master <- merge(master, eligibleScaled, by=c("Store","Category","Category_CG","Climate_Group",paste0("BA_Prod_",target),"Space",target), all.x=TRUE)
    
    # Use 1's and 0's for any data points that were not part of curve-fitting
    master[,paste0("Scaled_Alpha_",target)][is.na(master[,paste0("Scaled_Alpha_",target)])] <- 0
    master[,paste0("Scaled_Shift_",target)][is.na(master[,paste0("Scaled_Shift_",target)])] <- 0
    master[,paste0("Scaled_Beta_",target)][is.na(master[,paste0("Scaled_Beta_",target)])] <- 1
    master[,paste0("Scaled_BP_",target)][is.na(master[,paste0("Scaled_BP_",target)])] <- 0
    
    # For drill downs, use assumption for store-category history filtered stores
    # TODO: Write code
    
  }
  
  # END curve-fitting
  
  # BEGIN bound-setting

  print('start bound setting')
  # Add name to category bound table and merge with master data set
  names(bound_input)[1] <- "Category"
  master <- merge(master, bound_input, by="Category",all.x=TRUE)

  # Apply category percent of space bounds to store-category level
  master$PCT_of_Space_Lower_Limit <- floor(master$PCT_Space_Lower_Limit*master$Space_to_Fill/increment)*increment
  master$PCT_of_Space_Upper_Limit <- ceiling(master$PCT_Space_Upper_Limit*master$Space_to_Fill/increment)*increment

  # Apply percent space change bound to store-category level (does not apply to drill-downs, so dummy values are used)
  if(jobType=="tiered"){
    master$PCT_Change_Lower_Limit <- pmax(0,floor(master$Space*(1-pct_chg_limit)/increment)*increment)
    master$PCT_Change_Upper_Limit <- ceiling(master$Space*(1+pct_chg_limit)/increment)*increment
  } else {
    master$PCT_Change_Lower_Limit <- 0
    master$PCT_Change_Upper_Limit <- master$PCT_of_Space_Upper_Limit
  }

  # Take the max of the lower and min of the upper as the preliminary bounds  
  master$Lower_Limit <- pmax(master$Space.Lower.Limit,master$PCT_Change_Lower_Limit,master$PCT_of_Space_Lower_Limit)  
  master$Upper_Limit <- pmin(master$Space.Upper.Limit,master$PCT_Change_Upper_Limit,master$PCT_of_Space_Upper_Limit)

  print('finished bounding')
  # Apply exception conditions for sales penetration threshold, exits, and where no sales curve was generated (Enhanced only)
  for(i in 1:nrow(master)){
    master$Sales_Pen[i] <- master$Sales[i]/sum(master$Sales[which(master$Store[i] == master$Store)])
  }
  print(head(master$Sales_Pen))
  print('enhanced only')
  if(methodology == "enhanced"){
    master$Lower_Limit <- 
      ifelse((master$Exit_Flag == 1 | master$Sales_Pen < sls_pen_thresh | master$Scaled_Alpha_Sales == 0), 0, master$Lower_Limit)
    master$Upper_Limit <- 
      ifelse((master$Exit_Flag == 1 | master$Sales_Pen < sls_pen_thresh | master$Scaled_Alpha_Sales == 0), 0, master$Upper_Limit)
  }else{
    master$Lower_Limit <- ifelse((master$Exit_Flag == 1 | master$Sales_Pen < sls_pen_thresh), 0, master$Lower_Limit)
    master$Upper_Limit <- ifelse((master$Exit_Flag == 1 | master$Sales_Pen < sls_pen_thresh), 0, master$Upper_Limit)
  }
  print('finished bounding excpetions')
  print('end enhanced only')
  # END bound-setting
  
#  master <- master[c("Store","Category","Lower_Limit","Upper_Limit",
#                     "Scaled_Alpha_Sales","Scaled_Shift_Sales","Scaled_Beta_Sales","Scaled_BP_Sales",
#                     "Scaled_Alpha_Units","Scaled_Shift_Units","Scaled_Beta_Units","Scaled_BP_Units",
#                     "Scaled_Alpha_Profit","Scaled_Shift_Profit","Scaled_Beta_Profit","Scaled_BP_Profit")]


  master <- master[c("Store","Category",'Space',"Lower_Limit","Upper_Limit",
                     "Scaled_Alpha_Sales","Scaled_Shift_Sales","Scaled_Beta_Sales","Scaled_BP_Sales","Space_to_Fill","Sales","Profit",'Units')]
  final_out <- list(master,ref) 
  
  return (final_out)
  
}

# # Initial parameter setting for curve fitting
# incr_test <- 250
# pct_chg_limit_test <- 5
# sls_pen_thresh_test <- 0
# type_test <-"tiered"
# meth_test <- "Traditional"

# # Read in data as CSV
# master_test <- read.csv(paste0(curr_prod_name,"_Data_Merging_Output_Adj.csv"), header=TRUE, sep=",")
# bound_input_test <- read.csv(paste0(curr_prod_name,"_Bound_Input.csv"), header=TRUE, sep=",")

# # Call function
# ptm <- proc.time()
# result = curvefitting_boundsetting(master_test,bound_input_test,incr_test,pct_chg_limit_test,sls_pen_thresh_test,type_test,meth_test)
# print(proc.time() - ptm)

# str_cat_results = as.data.frame(result[1])
# analytics_reference = as.data.frame(result[2])

# # Write output to CSV
# write.csv(str_cat_results,paste0(curr_prod_name,"_Curve_Fitting_Results.csv"),row.names = FALSE)
# write.csv(analytics_reference,paste0(curr_prod_name,"_Analytics_Reference.csv"),row.names = FALSE)