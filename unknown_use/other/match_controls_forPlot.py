'''
Created on Jun 24, 2018

@author: Mark Holton
'''

import getopt, sys
import pandas as pd
import numpy as np
import qiime2
import time


from qiime2 import Metadata
from collections import defaultdict

def get_user_input_query_lines(user_input_file_of_queries):
    '''
    converts user_input_file_of_queries file into a list of strings that represent the lines of the file

    Parameters
    ----------
    user_input_file_of_queries : string
        file that contains lines of stings  
    
    Returns
    -------
     if user_input_file_of_queries is not ''
        list of strings that are the lines of the file
     if user_input_file_of_queries is ''
         returns False boolean
    '''
    if user_input_file_of_queries == '':
        print('null query')
        return False
    return open('./%s'%(user_input_file_of_queries),'r').readlines()


def keep_samples(original_MD, keep_query_lines):
    '''
    Filters out unwanted rows based on values in chosen columns.
    
    Parameters
    ----------
    original_MD : Metadata object
        Metadata object with all samples 
    
    keep_query_lines : array of strings
        list of strings that are the lines of the file
        each string is a sqlite query that determines what ids to keep

    Returns
    -------
    shrunk_MD : Metadata object
        original_MD input except that desired exclution has been applied so only the samples that match the input querys
        are kept
    '''
    shrunk_MD = original_MD
    try:
        shrunk_MD = shrunk_MD.filter_ids(shrunk_MD.get_ids(' AND '.join(keep_query_lines)))
    except:
        print('No samples fulfill keep queries. Exited while filtering out unwanted samples')
        sys.exit(1)
        
    return shrunk_MD
    

def determine_cases_and_controls(afterExclusion_MD, query_line_dict, case_controlDF):
    '''
    Determines what samples are cases or controls using the queries in query_line_array. The labels of each sample are 
    stored in case_controlDF
    
    Parameters
    ----------
    afterExclusion_MD : Metadata object
        Metadata object with unwanted samples filtered out
        
    query_line_array : array of 2 arrays of strings
        the arrays of strings are arrays of queries
        the first array are make of queries to determine controls
        the second array are make of queries to determine cases

        
    case_controlDF : dataframe
        dataframe with one column named case_control. The indexs are the same as the indexs of afterExclution_MD
        all values are Undefined
        
    Returns
    -------
    case_controlDF : dataframe
        dataframe with one column named case_control. The indexs are the same as the indexs of afterExclution_MD  
        values reflect if the index is a case, control, or Undefined
    '''
    afterExclusion_MD_full = afterExclusion_MD
    #change case_or_control to reflect that the next loop of queries in query_lines will filter based on control queries
   
    for key in query_line_dict:
        if key != 'case' and key != 'control':
            continue
        #resets afterExclution_MD so that filtering down to control samples does not influence filtering down to case
        shrunk_MD = afterExclusion_MD_full
            
        query_lines = query_line_dict[key]
        try:
            shrunk_MD = shrunk_MD.filter_ids(shrunk_MD.get_ids(' AND '.join(query_lines)))
        except:
            print('No samples fulfill %s queries. Exited while determining %s samples'%(key, key))
            sys.exit(1)
        ids = shrunk_MD.ids
        
        #replaces the true values created by the loop above to case or control
        case_controlDF.loc[ids,'case_control'] = key

    
    return case_controlDF


def merge_case_controlDF_and_afterExclutionMD(afterExclusion_MD, case_controlDF):
    '''
    Combines case_controlDF with afterExclution_MD and returns it as a metadata object
    
    Parameters
    ----------
    afterExclusion_MD : Metadata object
        Metadata object with unwanted samples filtered out
        
    case_controlDF : dataframe
        dataframe with one column named case_control. The indexs are the same as the indexs of afterExclution_MD  
        values reflect if the index is a case, control, or Undefined
        
    Returns
    -------
    Metadata(returnedMD) : Metadata object
        Metadata object with unwanted samples filtered out and a case_control column that reflects if the index is 
        a case, control, or Undefined    
    '''
    #turns case_controlDF into a metadata object
    case_controlMD = Metadata( case_controlDF)
    index_header_name = afterExclusion_MD.id_header
    #merges afterExclution_MD and case_controlMD into one new metadata object
    mergedMD = Metadata.merge(afterExclusion_MD, case_controlMD)

    return mergedMD


def filter_prep_for_matchMD(merged_MD, match_condition_lines, null_value_lines):
    '''
    filters out samples that do not have valid entries for columns that determine matching
    
    Parameters
    ----------
    merged_MD : Metadata object
        has case_control with correct labels but some samples might not have all matching information
    
    match_condition_lines : array of strings
        contains conditons to match samples on. In this function it is used only to get the columns for matching.

    Returns
    -------
    returned_MD : Metadata object
        Samples that do not have valid entries for columns that determine matching are removed. Everything else is the
        same as merged_MD.
    '''
    returned_MD = merged_MD
    for condition in match_condition_lines:
        column = condition.split('\t')[1].strip()
        try:
            returned_MD.get_column(column)
        except:
            print('Column %s not found in your input data. Correct this error in your --match/-m file'%(column))
            sys.exit(1)
        try:
            ids = returned_MD.get_ids(column + ' NOT IN ' + null_value_lines[0])
        except:
            print('No samples pass null filter queries. Exited while determining non null samples')
            sys.exit(1)
        #shrinks the MD so that future ids do not include samples that fail past queries
        returned_MD = returned_MD.filter_ids(ids)

    return returned_MD



def orderDict(dictionary, value_frequency):
    '''
    orders the elements of each array that is associated with a sample key by how often they get matched to other samples
    least to greatest
    
    Parameters
    dictionary: dictionary
        keys are linked to arrays that contain strings that correspond to samples that match to the
        sample the key represents
        
    value_frequency: dictionary
        keys are samples found in arrays of dictionary elements are numerical representation of 
        how many samples it matches to 
    
    Returns
    dictionary_to_return: dictionary
        dictionary with elements of the arrays that correspond to keys ordered from least to greatest abundance
    '''
    dictionary_to_return = dictionary.copy()
    for key in dictionary_to_return:
        unordered_array = dictionary_to_return[key]
        if len(unordered_array) == 0:
            continue
        #ordered_array will store the elements linked to key in their proper order    
        ordered_array = []
        count = 0
        while count < len(unordered_array):
            value = unordered_array[count]
            index = 0 #this index is for going through when sorting
            while index < len(ordered_array):
                ordered_value = ordered_array[index]
                if value_frequency[ordered_value] > value_frequency[value]:
                    ordered_array.insert(index,value)
                    break
                index = index + 1
            if index == len(ordered_array):
                ordered_array.insert(index,value)
                
            count = count + 1
        #overrides the unordered array linked to key with its ordered array
        dictionary_to_return[key] = ordered_array

    return dictionary_to_return





def order_keys(dictionary):
    '''
    orders the keys of a dictionary so that they can be used properly as the freemen of stable marriage 

    Parameters
    dictionary
        dictionary of cases or controls with their matching controls or cases ordered 
        by rising abundance
    
    Return
    keys_greatest_to_least: list
        contains keys in order of greatest to least amount of samples they match to
    '''
    keys_greatest_to_least = []
    for key in dictionary:
        if keys_greatest_to_least == []:
            keys_greatest_to_least.append(key)
            continue
        abundance_of_key_values = len(dictionary[key])
        index = 0
        for list_key in keys_greatest_to_least:
            abundance_of_list_key_values = len(dictionary[list_key])
            if abundance_of_key_values > abundance_of_list_key_values:
                keys_greatest_to_least.insert(index, key)
                break
            index = index + 1
        if index == len(keys_greatest_to_least):
            keys_greatest_to_least.append(key)

    return keys_greatest_to_least


def stable_marriage(dictionary_pref, pref_counts_cont, pref_counts_case):
    '''
    based on code shown by Tyler Moore in his slides for Lecture 2 for CSE 3353, SMU, Dallas, TX
    these slides can be found at https://tylermoore.ens.utulsa.edu/courses/cse3353/slides/l02-handout.pdf
    
    Gets back the best way to match samples to eachother to in a one to one manner. Best way refers to getting back the 
    most amount of one to one matches. 
    Note:
        If the keys of dictionary_pref are case samples the keys of one_to_one_match_dictionary will be control samples
    
    Parameters
    dictionary_pref: dictionary
        dictionary_pref is a dictionary of cases or controls with their matching controls or cases ordered 
        by rising abundance
    
    pref_counts: dictionary
        pref_counts is a dictionary with the frequency controls or cases match to something in dictionary_pref
    
    Returns
    one_to_one_match_dictionary: dictionary
        dictionary with keys and their corresponding values representing a match between a case and control sample
    '''
  
    free_keys = order_keys(dictionary_pref)
 
    one_to_one_match_dictionary = {}
    while free_keys :
        key = free_keys.pop()
        if len(dictionary_pref[key]) == 0:
            continue
        #get the highest ranked woman that has not yet been proposed to
        entry = dictionary_pref[key].pop()
        if entry not in one_to_one_match_dictionary: 
            one_to_one_match_dictionary[entry] = key
        else:
            key_in_use = one_to_one_match_dictionary [entry]
            if pref_counts_case[key] < pref_counts_case[key_in_use]:
                one_to_one_match_dictionary[entry] = key
                free_keys.append(key_in_use)
            else:
                free_keys.append(key)
    return one_to_one_match_dictionary





def match_samples(prepped_for_match_MD, conditions_for_match_lines):
    '''
    matches case samples to controls and puts the case's id in column matched to on the control sample's row
    
    Parameters
    ----------
    prepped_for_match_MD : Metadata object
        Samples that do not have valid entries for columns that determine matching are removed. Everything else is the
        same as merged_MD.
    
    conditions_for_match_lines : dataframe
        contains information on what conditions must be met to constitue a match
    
    Returns
    -------
    masterDF : dataframe
        masterDF with matches represented by a column called matched to. Values in matched to are sample id of the case
        sample the control sample matches to or 1 if it is a case sample
    
    '''
    case_dictionary = {}
    control_dictionary = {}
    control_match_count_dictionary = {}
    case_match_count_dictionary = {}
    
    matchDF = prepped_for_match_MD.to_dataframe()
    case_for_matchDF = matchDF[matchDF['case_control'].isin(['case'])]
    # creates column to show matches. since it will contain the sample number it was matched too the null value will be 0
    matchDF['matched_to'] = '0'

    

    # loops though case samples and matches them to controls
    for case_index, case_row in case_for_matchDF.iterrows():
        #print('case index is %s'%(case_index))
        
        # set matchDF to be only the samples of masterDF that are control samples
        controlDF = matchDF.copy()
        controlDF = controlDF[controlDF['case_control'].isin(['control'])]

        # loop though input columns to determine matches
        for conditions in conditions_for_match_lines:
            
            column_name = conditions.split('\t')[1].strip()
            
            # get the type of data for the given column. This determine how a match is determined
            if conditions.split('\t')[0] == 'range':
                num = conditions.split('\t')[2].strip()
                try:
                    row_num = float(case_row[column_name])
                except:
                    print('%s is not a a valid number'%(case_row[column_name]))
                    sys.exit(1)
                    
                try:
                    fnum = float(num)
                except:
                    print('%s is not a a valid number'%(num))
                    sys.exit(1)    
                          
                try:
                    nums_in_column = pd.to_numeric(controlDF[column_name])
                except:
                    print('column %s contains a string that can not be converted to a numerical value'%(column_name))
                    sys.exit(2)
                          
                # filters controls based on if the value in the control is not within a given distance form the case
                controlDF = controlDF[
                                    ( nums_in_column >= ( row_num - fnum ) ) 
                                    &
                                    ( nums_in_column <= ( row_num + fnum ) )
                                    ] 
            else:
                # filters controls if the strings for the control and case don't match
                controlDF = controlDF[controlDF[column_name].isin([case_row[column_name]])]
        case_dictionary.update({case_index:controlDF.index.values})
            
        # sets the matched to column of masterDF to the case sample ID for the control samples still left in matchDF
        #sets the control sample 'matched to' value to sample id in master_frame which is the same as the case's index
        #matchDF['matched_to'] = np.where(matchDF.index.isin(controlDF.index), matchDF['matched_to'] +' ' + case_index, matchDF['matched_to'] )
        
        for id_control in controlDF.index:
            if id_control not in control_match_count_dictionary:
                control_match_count_dictionary.update({id_control:0})
            control_match_count_dictionary.update({id_control:(control_match_count_dictionary[id_control]+1)})
            
            '''if id_control not in control_dictionary:
                control_dictionary.update({id_control:[case_index]})
            else:
                control_dictionary[id_control].append(case_index)'''
                          
        '''if case_index not in case_match_count_dictionary:
            case_match_count_dictionary.update({case_index:0})'''
        case_match_count_dictionary.update({case_index:(controlDF.index.values.size)})
        

        
    '''control_orig = control_dictionary.copy()
    control_dictionary = orderDict(control_dictionary, case_match_count_dictionary)
    control_to_case_match = stable_marriage(control_dictionary.copy(), control_match_count_dictionary)
    control_dictionary = control_orig'''
    
    
    print('start of stable marriage')
    sm_start = time.clock()
    case_orig = case_dictionary.copy()
    case_dictionary = orderDict(case_dictionary, control_match_count_dictionary)
    
    case_to_control_match = stable_marriage(case_dictionary.copy(), control_match_count_dictionary, case_match_count_dictionary)
    case_dictionary = case_orig
    sm_end = time.clock()
    print('time to get stable marriage done is %s'%(sm_end - sm_start))
    

    for key in case_to_control_match:
        key_value = case_to_control_match[key]
        matchDF.loc[ key, 'matched_to'] = key_value
        matchDF.loc[ key_value, 'matched_to'] = key
        
        
        

    
    return Metadata(matchDF) 




plotDF = pd.read_csv('data_plot.csv',  sep = '\t')
plotDF = plotDF.set_index('id')





tstart = time.clock()

# reading in commandline arguments
all_arguments = sys.argv
# selecting all arguments after python file name
argumentList = all_arguments[1:]
unixOptions = "i:k:c:e:n:m:o:"
gnuOptions = ["inputData=", "keep=", "control=", "case=", "nullValues=", "match=", "output=", "id=","conditions="]

try:  
    arguments, values = getopt.getopt(argumentList, unixOptions, gnuOptions)
except getopt.error as err:  
    # output error, and return with an error code
    print (str(err))
    sys.exit(2)
   

#metadata file
file_of_metadata = ''
user_input_file_name_exclude = ''
user_input_file_name_control = ''
user_input_file_name_experiment = ''
user_input_file_null_values = ''
user_input_file_name_match = ''    

id_value = ''
conditions = ''
# evaluate given options
#print(arguments)

for currentArgument, currentValue in arguments:  
    if currentArgument in ("-v", "--verbose"):
        print ("enabling verbose mode")
    elif currentArgument in ("-h", "--help"):
        print ("displaying help")
    elif currentArgument in ("-i", "--inputData"):
        file_of_metadata = currentValue
    elif currentArgument in ("-k", "--keep"):
        user_input_file_name_exclude = currentValue
    elif currentArgument in ("-c", "--control"):
        user_input_file_name_control = currentValue
    elif currentArgument in ("-e", "--case"):
        user_input_file_name_experiment = currentValue
    elif currentArgument in ("-n", "--nullValues"):
        user_input_file_null_values = currentValue
    elif currentArgument in ("-m", "--match"):
        user_input_file_name_match = currentValue
    elif currentArgument in ("-o", "--output"):
        outputFileName = currentValue
    elif currentArgument in ("--id"):
        id_value = currentValue
    elif currentArgument in ("--conditions"):
        conditions = currentValue    

if file_of_metadata == '':
    print('metadata file not found')
    sys.exit(2)
if outputFileName == '':
    print('output put file name not entered')
    sys.exit(2)
#read metadata file into metadata object
originalMD = Metadata.load( file_of_metadata )
        
#each line is a sqlite query to determine what samples to keep
exclude_query_lines_input = get_user_input_query_lines(user_input_file_name_exclude)
#each line is a sqlite query to determine what samples to label control
control_query_lines_input = get_user_input_query_lines(user_input_file_name_control)
#each line is a sqlite query to determine what samples to label case
case_query_lines_input = get_user_input_query_lines(user_input_file_name_experiment)
null_values_lines_input = get_user_input_query_lines(user_input_file_null_values)

'''
each line is tab seperated
the first element is the type of match: range or exact
    range matches samples if the numerical values compared are with in some other number of eachother
        this is only to be used with numerical values
    exact matches samples if the values compared are exactly the same
        this can be used for strings and numbers
the second element is the column to compare values of for the case and control samples
the third element is the range number or = (if the match type is exact) 
    this determines how far away a sample can be from another sample for the given column to be matched
'''
match_condition_lines_input = get_user_input_query_lines(user_input_file_name_match)

tloadedFiles = time.clock() 
print('time to load input files is %s'%(tloadedFiles - tstart))


if exclude_query_lines_input != False:
    afterExclusionMD = keep_samples(originalMD, exclude_query_lines_input)
else:
    afterExclusionMD = originalMD

tkeep = time.clock() 
print('time to filter out unwanted samples is %s'%(tkeep - tloadedFiles))
    
if case_query_lines_input != False and control_query_lines_input != False:
    ids = afterExclusionMD.get_ids()
    case_control_Series = pd.Series( ['Unspecified'] * len(ids), ids)
    '''
    ['Unspecified'] * len(ids) creates a list of elements. The list is the 
    same length as ids. All the elements are 'Unspecified'
    '''
    case_control_Series.index.name = afterExclusionMD.id_header
    case_controlDF = case_control_Series.to_frame('case_control') 
    case_control_dict = {'case':case_query_lines_input, 'control':control_query_lines_input }

    case_controlDF = determine_cases_and_controls(afterExclusionMD, case_control_dict, case_controlDF)
    case_controlMD = merge_case_controlDF_and_afterExclutionMD(afterExclusionMD, case_controlDF)
else:
    afterExclusionMD.to_dataframe().to_csv(outputFileName, sep = '\t')
    print('keep exit')
    sys.exit(0)
    
tcase_control = time.clock() 
print('time to get case and control samples %s'%(tcase_control - tkeep))
    
if null_values_lines_input == False or match_condition_lines_input == False:
    prepped_for_matchMD = case_controlMD
    print('no nulls')
else:    
    prepped_for_matchMD= filter_prep_for_matchMD(case_controlMD, match_condition_lines_input, null_values_lines_input)

    
tprepped = time.clock() 
print('time to prep Metadata information for match is %s'%(tprepped - tcase_control))

if match_condition_lines_input != False:
    matchedMD = match_samples( prepped_for_matchMD, match_condition_lines_input )
    matchedMD.to_dataframe().to_csv(outputFileName, sep = '\t')

tmatch = time.clock()  
tend = time.clock()
print('time to match is %s'%(tmatch- tprepped))
print('time to do everything %s'%(tend-tstart))



plotDF = plotDF.append(pd.Series( {'dataset':file_of_metadata, 'conditions':conditions, 'case_control':(tcase_control- tkeep), 'match':(tmatch- tprepped), 'total':(tend-tstart), 'null_filter':(tprepped - tcase_control), 'keep':(tkeep - tloadedFiles), 'load':(tloadedFiles - tstart)}).rename(id_value) )

plotDF.to_csv('data_plot.csv', sep = '\t')


