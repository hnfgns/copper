# coding=utf-8
from __future__ import division
import os
import io
import json
import copper
import numpy as np
import pandas as pd

class Dataset(dict):
    '''
    Wrapper around pandas to define metadata to a pandas DataFrame.
    Also introduces a some utils for filling missing data, statistics and ploting.
    '''

    # Constants
    NUMBER = 'Number'
    CATEGORY = 'Category'

    ID = 'ID'
    INPUT = 'Input'
    TARGET = 'Target'
    REJECT = 'Reject'
    REJECTED = 'Reject'

    def __init__(self, data=None):
        '''
        Creates a new Dataset

        Parameters
        ----------
            data: str with the path of the data. Or pandas.DataFrame.
        '''
        self.frame = None
        self.role = None
        self.type = None

        if data is not None:
            if type(data) is pd.DataFrame:
                self.set_frame(data)
            elif type(data) is str:
                self.load(data)

    # --------------------------------------------------------------------------
    #                                 LOAD
    # --------------------------------------------------------------------------

    def _id_identifier(self, col_name):
        '''
        Indentifier for Role=ID based on the name of the column
        '''
        return col_name.lower() in ['id']

    def _target_identifier(self, col_name):
        '''
        Indentifier for Role=Target based on the name of the column
        '''
        return col_name.lower() in ['target']

    def load(self, file_path):
        ''' Loads a csv file from the project data directory.

        Parameters
        ----------
            file_path: str
        '''
        filepath = os.path.join(copper.project.data, file_path)
        self.set_frame(pd.read_csv(filepath))

    def set_frame(self, frame, metadata=True):
        ''' Sets the frame of the Dataset and Generates metadata for the frame

        Parameters
        ----------
            frame: pandas.DataFrame
        '''
        self.frame = frame
        self.columns = self.frame.columns.values
        self.role = pd.Series(index=self.columns, name='Role', dtype=str)
        self.type = pd.Series(index=self.columns, name='Type', dtype=str)

        # Roles
        id_cols = [c for c in self.columns if self._id_identifier(c)]
        if len(id_cols) > 0:
            self.role[id_cols] = 'ID'

        target_cols = [c for c in self.columns if self._target_identifier(c)]
        if len(target_cols) > 0:
            # Set only variable to be target
            self.role[target_cols[0]] = self.TARGET
            self.role[target_cols[1:]] = self.REJECTED

        rejected = self.percent_missing()[self.percent_missing() > 0.5].index
        self.role[rejected] = self.REJECTED
        self.role = self.role.fillna(value=self.INPUT) # Missing cols are Input

        # Types
        number_cols = [c for c in self.columns
                              if self.frame.dtypes[c] in (np.int64, np.float64)]
        self.type[number_cols] = self.NUMBER
        self.type = self.type.fillna(value=self.CATEGORY)

    # --------------------------------------------------------------------------
    #                                PROPERTIES
    # --------------------------------------------------------------------------

    def get_inputs(self):
        '''
        Generates and returns a DataFrame with the inputs ready for doing
        Machine Learning

        Returns
        -------
            df: pandas.DataFrame
        '''
        return self.filter(role=self.INPUT)

    inputs = property(get_inputs)

    def get_target(self):
        '''
        Generates and returns a DataFrame with the targets ready for doing
        Machine Learning

        Returns
        -------
            df: pandas.Series
        '''
        return self.filter(role=self.TARGET).ix[:, 0]

    target = property(get_target)

    def get_numbers(self):
        ''' Returns the columns of type number
        '''
        return self.filter(type=self.NUMBER)

    numbers = property(get_numbers)


    def get_categories(self):
        ''' Returns the columns of type category
        '''
        return self.filter(type=self.CATEGORY)

    categories = property(get_categories)

    def get_metadata(self):
        '''
        Generates and return a DataFrame with a summary of the data:
            * Role
            * Missing values

        Returns
        -------
            pandas.DataFrame with the role and type of each column
        '''
        metadata = pd.DataFrame(index=self.columns)
        metadata['Role'] = self.role
        metadata['Type'] = self.type
        metadata['dtype'] = self.frame.dtypes
        return metadata

    metadata = property(get_metadata)

    def update(self):
        ''' Updates the frame based on the metadata
        '''
        for col in self.frame.columns:
            if self.type[col] == self.NUMBER and \
                                        self.frame[col].dtype == object:
                self.frame[col] = self.frame[col].apply(copper.transform.to_number)

    def filter(self, role=None, type=None, ret_cols=False, ret_ds=False):
        ''' Filter the columns of the Dataset by Role and Type

        Parameters
        ----------
            role: Role constant
            type: Type constant
            columns: boolean, True if want only the column names

        Returns
        -------
            pandas.DataFrame
        '''
        # Note on this funcion python.type(...) is replaced by the type argument
        def _type(obj):
            return obj.__class__

        if role is None:
            role = [self.ID, self.INPUT, self.TARGET, self.REJECTED]
        elif _type(role) == str:
            role = [role]

        if type is None:
            type = [self.NUMBER, self.CATEGORY]
        elif _type(type) == str:
            type = [type]

        cols = [col for col in self.columns.tolist() 
                        if self.role[col] in role and self.type[col] in type]
        
        if ret_cols:
            return cols
        elif ret_ds:
            ds = Dataset(self.frame[cols])
            for col in ds.columns:
                ds.role[col] = self.role[col]
                ds.type[col] = self.type[col]
            return ds
        else:
            return self.frame[cols]


    # --------------------------------------------------------------------------
    #                                    STATS
    # --------------------------------------------------------------------------

    def unique_values(self, ascending=False):
        '''
        Generetas a Series with the number of unique values of each column
        Note: Excludes NA

        Parameters
        ----------
            ascending: boolean, sort the returned Series on this direction

        Returns
        -------
            pandas.Series
        '''
        return copper.utils.frame.unique_values(self.frame, ascending=ascending)

    def percent_missing(self, ascending=False):
        '''
        Generetas a Series with the percent of missing values of each column

        Parameters
        ----------
            ascending: boolean, sort the returned Series on this direction

        Returns
        -------
            pandas.Series
        '''
        return copper.utils.frame.percent_missing(self.frame, ascending=ascending)

    def variance_explained(self, cols=None, plot=False):
        '''
        NOTE 1: fill/impute missing values before using this
        NOTE 2: only use columns with dtype int or float

        Parameters
        ----------
            cols: list, of columns to use in the calculation, default all inputs
            plot: boolean, True want to make a bar plot

        Returns
        -------
            pandas Series and plot it ready to be shown
        '''
        if cols is None:
            frame = self.filter(role=self.INPUT, type=self.NUMBER)
        else:
            frame = self.frame

        U, s, V = np.linalg.svd(frame.values)
        variance = np.square(s) / sum(np.square(s))
        
        if plot:
            xlocations = np.array(range(len(variance)))+0.5
            width = 0.95
            plt.bar(xlocations, variance, width=width)
            plt.xlabel("Columns")
            plt.ylabel("Variance Explained")
        return variance

    def corr(self, cols=None, ascending=False):
        ''' Correlation between inputs and target
        If a column has a role of target only values for that column are returned.
        If not columns then the pandas.corr is called on the inputs.

        Parameters
        ----------
            cols: list, list of columns on the returned DataFrame.
                        default=None: On that case if there is a column with
                        role=Target then retuns only values for that column if
                        there is not return all values
            cols: str, special case: 'all' to return all values

        Returns
        -------
        '''
        if cols is None:
            try :
                # If there is a target column use that
                cols = self.role[self.role == self.TARGET].index[0]
            except:
                cols = [c for c in self.columns
                              if self.frame.dtypes[c] in (np.int64, np.float64)]
        elif cols == 'all':
            cols = [c for c in self.columns
                              if self.frame.dtypes[c] in (np.int64, np.float64)]

        corrs = self.frame.corr()
        corrs = corrs[cols]
        if type(corrs) is pd.Series:
            corrs = corrs[corrs.index != cols]
            return corrs.order(ascending=ascending)
        else:
            return corrs

    def fillna(self, cols=None, method='mean', value=None):
        '''
        Fill missing values

        Parameters
        ----------
            cols: list, of columns to fill missing values
            method: str, method to use to fill missing values
                * mean(numerical,money)/mode(categorical): use the mean or most
                  repeted value of the column
                * knn
        '''
        if cols is None:
            cols = self.columns
        if type(cols) == str:
            cols = [cols]

        if method == 'mean' or method == 'mode':
            for col in cols:
                if self.role[col] != self.REJECTED:
                    if self.type[col] == self.NUMBER:
                        if method == 'mean' or method == 'mode':
                            value = self[col].mean()
                    if self.type[col] == self.CATEGORY:
                        if method == 'mean' or method == 'mode':
                            value = self[col].value_counts().index[0]
                    self[col] = self[col].fillna(value=value)
        elif method == 'knn':
            # TODO: FIX
            for col in cols:
                imputed = copper.r.imputeKNN(self.frame)
                self.frame[col] = imputed[col]
        elif value is not None:
            for col in cols:
                if self.role[col] != self.REJECTED:
                    if type(value) is str:
                        if self.role[col] != self.CATEGORY:
                            self[col] = self[col].fillna(value=value)
                    elif type(value) is int or type(value) is float:
                        if self.role[col] != self.NUMBER:
                            self[col] = self[col].fillna(value=value)

    def fix_names(self):
        ''' 
        Removes spaces and symbols from column names
        Those symbols generates error if using patsy
        '''
        # TODO: change to regexp
        new_cols = self.columns.tolist()
        symbols = ' .-'
        for i, col in enumerate(new_cols):
            for symbol in symbols:
                new_cols[i] = ''.join(new_cols[i].split(symbol))
        self.frame.columns = new_cols
        self.columns = new_cols
        self.role.index = new_cols
        self.type.index = new_cols

    # --------------------------------------------------------------------------
    #                                    CHARTS
    # --------------------------------------------------------------------------

    def histogram(self, col, **args):
        '''
        Draws a histogram for the selected column on matplotlib

        Parameters
        ----------
            col:str, column name
            bins: int, number of bins of the histogram, default 20
            legend: boolean, True if want to display the legend of the ploting
            ret_list: boolean, True if want the method to return a list with the
                                distribution(information) of each bin

        Return
        ------
            nothing, figure is ready to be shown
        '''
        copper.plot.histogram(self.frame[col], **args)

    # --------------------------------------------------------------------------
    #                    SPECIAL METHODS / PANDAS API
    # --------------------------------------------------------------------------

    def __unicode__(self):
        return self.metadata

    def __str__(self):
        return str(self.__unicode__())

    def __getitem__(self, name):
        return self.frame[name]

    def __setitem__(self, name, value):
        self.frame[name] = value

    def __len__(self):
        return len(self.frame)

    def head(self, n=5):
        return self.frame.head(n)

    def tail(self, n=5):
        return self.frame.tail(n)

    def get_values(self):
        ''' Returns the values of the dataframe
        '''
        return self.frame.values

    values = property(get_values)

def join(ds1, ds2, others=[], how='outer'):
    others.insert(0, ds2)
    others.insert(0, ds1)

    df = None
    for ds in others:
        if df is not None:
            df = df.join(ds.frame, how=how)
        else:
            df = ds.frame

    ans = Dataset(df)
    for ds in others:
        for index, row in ds.metadata.iterrows():
            ans.role[index] = row['Role']
            ans.type[index] = row['Type']

    return ans