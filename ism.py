"""ism.py
module to cause dispersion
"""
from __future__ import (absolute_import, division,
                        print_function, unicode_literals)
import numpy as np
import scipy as sp
from scipy import signal
from . import PSS_utils as utils
from . import scintillation as scint

__all__ = ['ISM','scintillate','convolve_with_profile','make_dm_broaden_tophat','make_scatter_broaden_exp']

class ISM(object):
    def __init__(self, Signal_in, DM = 30, mode='explore'):
        self.Signal_in = Signal_in
        self.signal = self.Signal_in.signal
        self.f0 = self.Signal_in.f0
        self.bw = self.Signal_in.bw
        self.Nf = self.Signal_in.Nf
        self.Nt = self.Signal_in.Nt
        self.TimeBinSize =self.Signal_in.TimeBinSize
        self.freqBinSize = self.Signal_in.freqBinSize
        self.first_freq = self.Signal_in.first_freq
        self.last_freq = self.Signal_in.last_freq
        self.freq_Array = self.Signal_in.freq_Array
        self.mode = mode
        self.DM = DM
        self.tau_scatter = None
        self.to_DM_Broaden = False
        self.to_Scatter_Broaden_exp = False
        self.to_Scatter_Broaden_stoch = False
        self.to_Scintillate = False
        self.time_dependent_scatter = False
        self.time_dependent_DM = False


    def finalize_ism(self):
        self.ISM_Dict = dict(tau_scatter = self.tau_scatter, DM = self.DM, dispersion=False, scattering=False, scintillation=False)
        self.ISM_Dict['to_DM_Broaden'] = self.to_DM_Broaden
        self.ISM_Dict['to_Scatter_Broaden_exp'] = self.to_Scatter_Broaden_exp
        self.ISM_Dict['to_Scatter_Broaden_stoch'] = self.to_Scatter_Broaden_stoch
        self.ISM_Dict['time_dependent_scatter'] = self.time_dependent_scatter
        self.ISM_Dict['time_dependent_DM'] = self.time_dependent_DM
        self.ISM_Dict['to_Scintillate'] = self.to_Scintillate
        if self.mode=='explore':
            raise ValueError('No Need to run finalize_ism() if simulator is in explore mode.')
        self.Signal_in.MetaData.AddInfo(self.ISM_Dict)

    def shiftit(self, y, shift):
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
        workifft = np.fft.ifft(work)
        return workifft.real

    def disperse(self):
        #Function to calculate the dispersion per frequency bin for 1/f^2 dispersion
        self.ISM_Dict['dispersion'] = True
        if self.Signal_in.SignalType=='intensity':
            #For intensity signal calculate dispersion for all sub-bands.
            self.K = 1.0/2.41e-4 #constant used to be more consistent with PSRCHIVE
            self.time_delays = -1e-3*self.K*self.DM*(np.power((self.freq_Array/1e3),-2)) #freq in MHz, delays in milliseconds
                #Dispersion as compared to infinite frequency
            self.time_delays = np.rint(self.time_delays//self.TimeBinSize) #Convert to number of bins
            self.widths = np.zeros(self.Nf)
            sub_band_width = self.bw/self.Nf
            for ii, freq in enumerate(self.freq_Array):
                self.signal[ii,:] = self.shiftit(self.signal[ii,:], self.time_delays[ii])
                width = int(utils.top_hat_width(sub_band_width, freq, self.DM)//self.TimeBinSize)
                if width > 0 and self.to_DM_Broaden:
                    if width > self.Nt:
                        raise ValueError('Too Much DM! Dispersion broadening top hat wider than data array!')
                    self.widths[ii] = width
                    self.signal[ii,:] = sp.signal.convolve(self.signal[ii,:], sp.signal.boxcar(width)/width, mode='same',method='fft').astype(self.Signal_in.data_type)
                    # The division by width of the boxcar filter normalizes the convolution

                    #print(self.freq_Array[ii],' MHz ','width=', width) #for debugging
        elif self.Signal_in.SignalType=='voltage':
            #For voltage signal disperse coherently.
            raise ValueError('Sorry, Voltage-type signal dispersion is not currently supported!')
            #for ii in range(4): #Maybe faster to do the complex fft with two channels.
            #    sig_FFT = np.fft.rfft(self.signal[ii,:])
            #    fft_len = len(sig_FFT)
            #    f_array = np.linspace(-(self.last_freq)*1e6,0,length2)
            #    disp_signal_fft = sig_FFT*np.exp(1j*2*np.pi*4.148808e9/((freq+f0)*f0**2)*DM*freq**2)
            #    self.signal[ii,:] = np.fft.irfft(disp_signal_fft)

        self.Signal_in.MetaData.AddInfo(self.ISM_Dict)

    def scatter(self, array, scat_timescale):
        """
        Simulate scatter broadening by convolving the signal with an exp(-t/tau).
        """
        nBins = self.Signal_in.MetaData.nBins_per_period
        tau = scat_timescale / self.TimeBinSize
        try:
            #N_taus = nBins/tau
            exp_time = np.linspace(0,nBins,nBins)
            scatter_exp = np.exp(-exp_time/tau)
            scatter_exp /= np.sum(scatter_exp)
            return sp.signal.convolve(array, scatter_exp, mode='full',method='fft')[:-nBins]
            #.astype(self.Signal_in.data_type)
        except: #Exception if meant for tau too small for given sampling rate.
            return array

class scintillate():
    def __init__(self, Signal_in, V_ISS = None,scint_bw = None, scint_timescale = None, pulsar= None, to_use_NG_pulsar=False, telescope=None, freq_band=None):
        """
        Uses a phase screen with the given power spectrum to scintillate a pulsar signal
        across an observation band. The class uses the parameters given to calculate
        thin phase screens and gain image using Fresnel propagation.

        The screens are calculated for the size appropriate to the given parameters
        and observation length.
        """

        if pulsar == None and V_ISS==None and scint_timescale==None:
            raise ValueError('Need to set a variable that sets the scintillation timescale.')

        if pulsar != None and to_use_NG_pulsar:
            if telescope==None or freq_band==None:
                raise ValueError('Must set both the telescope and bandwidth for {0}.'.format(pulsar))

            self.scint_bw, self.scint_time = self.NG_scint_param(pulsar, telescope, freq_band)

            if scint_timescale != None:
                print('Overiding scint_timescale value. Scintillation timescale set to {0} using Lam, et al. 2015.'.format(self.scint_time))
                print('Change to_use_NG_pulsar flag to use entered value.')
            if V_ISS != None :
                print('Overiding V_ISS value. Scintillation timescale set to {0} using Lam, et al. 2015.'.format(self.scint_time))
                print('Change to_use_NG_pulsar flag to use entered value.')

        if pulsar == None and V_ISS==None and scint_timescale!=None:
            self.scint_time = scint_timescale
            self.scint_bw = scint_bw
        if pulsar == None and V_ISS!=None and scint_timescale==None:
            raise ValueError('V_ISS calculation not currently supported.')

        #Should calculate Number_r_F for the particular scint_time.

        diff_phase_screen = scint.phase_screen(Signal_in, Nx=400, Ny=150,Freq_DISS=self.scint_bw, Number_r_F=1/128.)

        L = np.rint(diff_phase_screen.xmax//diff_phase_screen.r_Fresnel)

        #refrac_phase_screen = scint.phase_screen(self.Signal_in, DM, Number_r_F=5)
        #Calculate a refraction screen to give a correction.

        self.gain = scint.images(diff_phase_screen, Signal_in, mode='simulation').gain
        self.scint_time_sample_rate = 10 #Samples per scintillation time
        self.to_Scintillate = True
        self.Scint_Dict= {}
        self.Scint_Dict['scint_time_sample_rate'] = self.scint_time_sample_rate
        self.Scint_Dict['scint_bw'] = self.scint_bw
        self.Scint_Dict['scint_time'] = self.scint_time
        self.Scint_Dict['to_Scintillate'] = self.to_Scintillate
        Signal_in.MetaData.AddInfo(self.Scint_Dict)

    def NG_scint_param(self, pulsar, telescope, freq_band):
        """ Method for pulling scintillation bandwidth (MHz) and scintillation timescale (sec)
        from a txt file.
        pulsar = Any of the NANOGrav pulsars from 9yr Data release in file.
                    See 'PTA_pulsar_nb_data.txt' for details.
        telescope  = 'AO' (Arecibo Obs) or 'GBT' (Greenbank Telescope)
        freq_band = [327 ,430, 820, 1400, 2300]
        """
        freq_bands_txt = np.array(['0.327','0.430','0.820','1.400','2.300'], dtype=str)
        freq_band = np.extract(freq_band==freq_bands_txt.astype(float)*1e3,freq_bands_txt)[0]

        search_list = (pulsar, telescope, freq_band)
        columns = (10,11)
        try:
            scint_bw, scint_timescale = utils.text_search(search_list, columns, 'PTA_pulsar_nb_data.txt')
        except:
            raise ValueError('Combination of pulsar {0}, telescope {1} and bandwidth {2} MHz'.format(pulsar, telescope, freq_band)+' not found in txt file.')

        return scint_bw, scint_timescale


def convolve_with_profile(pulsar_object,input_array):
    """
    General convolution function. Takes an input array made in other functions
    to convolve with the pulse profile.
    
    Parameters
    ---
    pulsar_object: VersionZeroPointZero.pulsar.Pulsar object
        The pulsar object
    input_array: somewhere
        Any array the user wants to convolve with the pulse profile
    """
    
    width = pulsar_object.nBinsPeriod
    for ii, freq in enumerate(pulsar_object.Signal_in.freq_Array):
        #Normalizing the pulse profile
        pulsar_prof_sum = np.sum(pulsar_object.profile[ii,:])
        pulsar_prof_norm = pulsar_object.profile[ii,:] / pulsar_prof_sum
        
        #Normalizing the input array
        input_array_sum = np.sum(input_array[ii,:])
        input_array_norm = input_array[ii,:] / input_array_sum
        
        #Convolving the input array with the pulse profile
        convolved_prof = sp.convolve(pulsar_prof_norm, input_array_norm,"full")
        
        #Renormalizing the convolved pulse profile
        pulsar_object.profile[ii,:] = (pulsar_prof_sum)*(convolved_prof[:width])

def make_dm_broaden_tophat(pulsar_object,signal_object):
    """
    This is a function that makes a 2-D array of top hat functions
    to convolve with the pulse profile and simulate DM broadening.
    Calls general convolution function to convolve with pulse profile.
    See PATH/TO/CONVOLUTION for more information.
       
    Parameters
    ---------
    pulsar_object: VersionZeroPointZero.pulsar.Pulsar object
        The pulsar object 
    signal_object: VersionZeroPointZero.signal.Signal
        The signal object
    
    Notes
    -----
    Also records the DM widths in the MetaData of the signal object.
    
    See Lorimer and Kramer 2006 section A2.4
    """ 
    
    dm_widths = np.zeros(pulsar_object.Nf)
    lowest_freq_top_hat_width = int(utils.top_hat_width(pulsar_object.bw / pulsar_object.Nf, pulsar_object.Signal_in.freq_Array[0], 100) // pulsar_object.TimeBinSize)    
    tophat_array = np.zeros((pulsar_object.Nf,lowest_freq_top_hat_width))
    
    for ii, freq in enumerate(pulsar_object.Signal_in.freq_Array):
        #Creating the top hat array
        
        sub_band_width = pulsar_object.bw / pulsar_object.Nf
        tophat_width = int(utils.top_hat_width(sub_band_width, freq, signal_object.MetaData.DM) // pulsar_object.TimeBinSize)
        if tophat_width > pulsar_object.Nt:
            raise ValueError('Too Much DM! Dispersion broadening top hat wider than data array!')
        dm_widths[ii] = tophat_width
        tophat = signal.boxcar(tophat_width)
        tophat_len=len(tophat)
        tophat = np.append(tophat,np.zeros(lowest_freq_top_hat_width-tophat_len))
        tophat_array[ii,:] = tophat

    Dict = {'dm_widths':dm_widths}
    signal_object.MetaData.AddInfo(Dict)   

    return tophat_array

def make_scatter_broaden_exp(pulsar_object, signal_object, tau_d_in=1):
    """
    This is a function that makes a 2-D array of exponential functions
    to convolve with the pulse profile and simulate scatter broadening.
    Calls general convolution function to convolve with pulse profile.
    See PATH/TO/CONVOLUTION for more information.

    Parameters
    ---------
    pulsar_object: VersionZeroPointZero.pulsar.Pulsar object
        The pulsar object 
    signal_object: VersionZeroPointZero.signal.Signal
        The signal object
    tau_d_in: VersionZeroPointZero.scintillation.scale_tau_d
        The scattering time
        In units of milliseconds, default 1ms
        See Cordes et al. 1990
    
    See Lorimer and Kramer 2006 section A2.5
    """
    
    width = pulsar_object.nBinsPeriod
    tau_scatter_time = scint.scale_tau_d(tau_d = tau_d_in,nu_i = signal_object.f0,nu_f = signal_object.freq_Array)
    tau_scatter_bins = tau_scatter_time / signal_object.TimeBinSize
    t = np.linspace(0,pulsar_object.T,width)
    EXP_array = np.zeros((pulsar_object.Nf,width))
    #Iterating over the tau arrays where each profile 
    #corresponds to the respective tau index
    for ii, tau_scatter in enumerate(tau_scatter_time): 
        EXP = (np.exp(-t/tau_scatter))
        EXP_array[ii,:] = EXP

    return EXP_array