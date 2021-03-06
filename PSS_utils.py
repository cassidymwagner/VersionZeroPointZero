"""
utils.py
A place to organize methods used by multiple modules
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
import numpy as np
import scipy as sp
import math
from scipy import ndimage
from scipy.signal import fftconvolve,correlate

def shiftit(y, shift):
    """
    shifts array y by amount shift (in sample numbers)
    uses shift theorem and FFT
    shift > 0  ==>  lower sample number (earlier)
    modeled after fortran routine shiftit
    Optimized from JMC's code by Michael Lam
    """
    #TODO Add Try Except for odd length arrays...
    yfft = np.fft.fft(y)
    size = np.size(y) #saves time
    constant = (shift*2*np.pi)/float(size) #needs a negative here for the right direction, put it in?
    theta = constant*np.arange(size)
    c = np.cos(theta)
    s = np.sin(theta)
    work = np.zeros(size, dtype='complex')
    work.real = c * yfft.real - s * yfft.imag
    work.imag = c * yfft.imag + s * yfft.real
    # enforce hermiticity
    half_size = int(size//2)
    work.real[half_size:] = work.real[half_size:0:-1]
    work.imag[half_size:] = -work.imag[half_size:0:-1]
    work[half_size] = 0.+0.j
    #work.real[size//2:] = work.real[size//2:0:-1]
    #work.imag[size//2:] = -work.imag[size//2:0:-1]
    #work[size//2] = 0.+0.j
    workifft = np.fft.ifft(work)
    return workifft.real

def down_sample(x, R): #Method to down sample an array by a factor
    #down_sample(array, downsampling factor)
    #This is fast, but not as general as possible

    x.reshape(-1, R)
    downsampled = x.reshape(-1, R).mean(axis=1)#/np.amax(x)

    return downsampled#*np.amax(x)/np.amax(downsampled)

def rebin(a, newLength):
    """rebin(old array, new number of bins)
    This is a very general downsampling rebinner, but has for loops and if
    statements, hence it is slower than down_sample().
    'a' must be a 1-d array
    """
    #TODO Make this code run faster. Vectorize
    newBins = np.linspace(0, a.size, newLength, endpoint=False)
    width = int(math.ceil(a.size/newLength))
    a_rebin=np.zeros((newLength,width))*np.nan
    #Using NaN means that we do not have extra zeros in the array that would get averaged
    row = 0
    column = 0
    for ii in range(0, a.size):
        if ii < (newBins[row] + newBins[1]):
            a_rebin[row,column] = a[ii]
            column +=1
        else:
            column = 0
            row += 1
            a_rebin[row,column] = a[ii]
            column +=1

    a_rebinned = sp.nanmean(a_rebin,axis=1)
    #NaN mean does not count NaNs in total
    return a_rebinned#*np.amax(a)/np.amax(a_rebinned)


def top_hat_width(sub_band_width, sub_bandwidth_center, DM):
    """
    Top Hat pulse to convolve with pulses for dipsersion broadening
    Given the bandwidth of the subbands and the center of the sub band
    calculates top_hat width in milliseconds.
    sub_band_width in MHz
    sub_bandwidth_center in GHz following
    (Lorimer and Kramer, 2005)"""
    th_width = 8.297616e-3 * DM * (sub_band_width) / (sub_bandwidth_center/1e3)**3 #width in milliseconds
    #freq converted to GHz for calculation above.
    return th_width

#def DM_broaden_signal(pulse, width):
#    """Convolves the pulses with a top hat pulse to DM broaden each pulse. """
#    in_max = np.amax(pulse)
#    top_hat = sp.signal.boxcar(width)/width
#    #convolved =
#    return np.convolve(width, pulse, 'same')
#    #return convolved*np.sum(convolve)/width

def block_mean(ar, fact): #Courteousy Mike T. Stack Overflow
    assert isinstance(fact, int), type(fact)
    sx, sy = ar.shape
    X, Y = np.ogrid[0:sx, 0:sy]
    regions = sy//fact * (X//fact) + Y//fact
    res = ndimage.mean(ar, labels=regions, index=np.arange(regions.max() + 1))
    res.shape = (int(sx//fact), int(sy//fact))
    return res

def savitzky_golay(y, window_size, order, deriv=0, rate=1): #Courteousy scipy recipes
    r"""Smooth (and optionally differentiate) data with a Savitzky-Golay filter.
    The Savitzky-Golay filter removes high frequency noise from data.
    It has the advantage of preserving the original shape and
    features of the signal better than other types of filtering
    approaches, such as moving averages techniques.
    Parameters
    ----------
    y : array_like, shape (N,)
        the values of the time history of the signal.
    window_size : int
        the length of the window. Must be an odd integer number.
    order : int
        the order of the polynomial used in the filtering.
        Must be less then `window_size` - 1.
    deriv: int
        the order of the derivative to compute (default = 0 means only smoothing)
    Returns
    -------
    ys : ndarray, shape (N)
        the smoothed signal (or it's n-th derivative).
    Notes
    -----
    The Savitzky-Golay is a type of low-pass filter, particularly
    suited for smoothing noisy data. The main idea behind this
    approach is to make for each point a least-square fit with a
    polynomial of high order over a odd-sized window centered at
    the point.
    Examples
    --------
    t = np.linspace(-4, 4, 500)
    y = np.exp( -t**2 ) + np.random.normal(0, 0.05, t.shape)
    ysg = savitzky_golay(y, window_size=31, order=4)
    import matplotlib.pyplot as plt
    plt.plot(t, y, label='Noisy signal')
    plt.plot(t, np.exp(-t**2), 'k', lw=1.5, label='Original signal')
    plt.plot(t, ysg, 'r', label='Filtered signal')
    plt.legend()
    plt.show()
    References
    ----------
    .. [1] A. Savitzky, M. J. E. Golay, Smoothing and Differentiation of
       Data by Simplified Least Squares Procedures. Analytical
       Chemistry, 1964, 36 (8), pp 1627-1639.
    .. [2] Numerical Recipes 3rd Edition: The Art of Scientific Computing
       W.H. Press, S.A. Teukolsky, W.T. Vetterling, B.P. Flannery
       Cambridge University Press ISBN-13: 9780521880688
    """
    import numpy as np
    from math import factorial

    try:
        window_size = np.abs(np.int(window_size))
        order = np.abs(np.int(order))
    except:# ValueError, msg:
        raise ValueError("window_size and order have to be of type int")
    if window_size % 2 != 1 or window_size < 1:
        raise TypeError("window_size size must be a positive odd number")
    if window_size < order + 2:
        raise TypeError("window_size is too small for the polynomials order")
    order_range = range(order+1)
    half_window = int((window_size -1) // 2)
    # precompute coefficients
    b = np.mat([[k**i for i in order_range] for k in range(-half_window, half_window+1)])
    m = np.linalg.pinv(b).A[deriv] * rate**deriv * factorial(deriv)
    # pad the signal at the extremes with
    # values taken from the signal itself
    firstvals = y[0] - np.abs( y[1:half_window+1][::-1] - y[0] )
    lastvals = y[-1] + np.abs(y[-half_window-1:-1][::-1] - y[-1])
    y = np.concatenate((firstvals, y, lastvals))
    return np.convolve( m[::-1], y, mode='valid')

def find_nearest(array,value):
    """Returns the argument of the element in an array nearest to value.
    For half width at value use array[max:].
    """
    diff=np.abs(array-value)
    idx = diff.argmin()
    if idx == 0 or array[1] < value:
        idx = 1
    return idx

def acf2d(array,speed='fast',mode='full',xlags=None,ylags=None):
    """Courteousy of Michael Lam's PyPulse
    Calculate the autocorrelation of a 2 dimensional array.
    """
    if speed == 'fast' or speed == 'slow':
        ones = np.ones(np.shape(array))
        norm = fftconvolve(ones,ones,mode=mode) #very close for either speed
        if speed=='fast':
            return fftconvolve(array,np.flipud(np.fliplr(array)),mode=mode)/norm
        else:
            return correlate(array,array,mode=mode)/norm
    elif speed == 'exact':
        #NOTE: (r,c) convention is flipped from (x,y), also that increasing c is decreasing y
        LENX = len(array[0])
        LENY = len(array)
        if xlags is None:
            xlags = np.arange(-1*LENX+1,LENX)
        if ylags is None:
            ylags = np.arange(-1*LENY+1,LENY)
        retval = np.zeros((len(ylags),len(xlags)))
        for i,xlag in enumerate(xlags):
            print(xlag)
            for j,ylag in enumerate(ylags):
                if ylag > 0 and xlag > 0:
                    A = array[:-1*ylag,xlag:] #the "stationary" array
                    B = array[ylag:,:-1*xlag]
                elif ylag < 0 and xlag > 0:
                    A = array[-1*ylag:,xlag:]
                    B = array[:ylag,:-1*xlag]
                elif ylag > 0 and xlag < 0:#optimize later via symmetries
                    A = array[:-1*ylag,:xlag]
                    B = array[ylag:,-1*xlag:]
                elif ylag < 0 and xlag < 0:
                    A = array[-1*ylag:,:xlag]
                    B = array[:ylag,-1*xlag:]
                else: #one of the lags is zero
                    if ylag == 0 and xlag > 0:
                        A = array[-1*ylag:,xlag:]
                        B = array[:,:-1*xlag]
                    elif ylag == 0 and xlag < 0:
                        A = array[-1*ylag:,:xlag]
                        B = array[:,-1*xlag:]
                    elif ylag > 0 and xlag == 0:
                        A = array[:-1*ylag,:]
                        B = array[ylag:,-1*xlag:]
                    elif ylag < 0 and xlag == 0:
                        A = array[-1*ylag:,:]
                        B = array[:ylag,-1*xlag:]
                    else:
                        A = array[:,:]
                        B = array[:,:]
                        #print xlag,ylag,A,B
                C = A*B
                C = C.flatten()
                goodinds = np.where(np.isfinite(C))[0] #check for good values
                retval[j,i] = np.mean(C[goodinds])
        return retval
def text_search(search_list, header_values, filepath, header_line=0, file_type='txt'):
    """ Method for pulling value from  a txt file.
    search_list = list of string-type values that demarcate the line in a txt file
                from which to pull values
    header_values = string of column headers or array of column numbers (in Python numbering)
                the values from which to pull
    filepath = file path of txt file. (string)
    header_line = line with headers for values.
    file_type = 'txt' or 'csv'

    returns: tuple of values matching header values for the search terms given.
    """
    #TODO Make work for other file types.
    #if file_type == 'txt':
    #    delimiter = ''
    #elif file_type == 'csv':
    #    delimiter = ','

    check = 0
    output_values = list()

    with open(filepath, 'r') as searchfile: # Find Column Numbers from column names
        if any(isinstance(elem, str) for elem in header_values):
            column_num = []
            parsed_header = list(searchfile.readlines()[header_line].split())
            for ii , header in enumerate(header_values):
                column_num.append(parsed_header.index(header))
        else:
            column_num = np.array(header_values)


    with open(filepath, 'r') as searchfile: # Find Values using search keys and column numbers.
        #TODO Don't know why I need this second with statement, but if I take it out it doesn't work.
        for line in searchfile:
            if all(ii in line for ii in search_list):

                info = line.split()
                for jj, value in enumerate(column_num):
                    output_values.append(info[value])
                check += 1

    if check == 0 :
        raise ValueError('Combination {0} '.format(search_list)+' not found in same line of text file.')
    if check > 1 :
        raise ValueError('Combination {0} '.format(search_list)+' returned multiple results in txt file.')

    return tuple([float(i) for i in output_values])

def debug_p(var):
    print(str(var) + ' = ', var)
