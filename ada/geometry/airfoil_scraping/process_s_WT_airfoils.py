import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
colors = ['#0065cc', '#e69f00', '#009e73', '#d55e00', '#56b4ff', '#fca7c7', '#ede13f', '#666666', '#000000']
matplotlib.rcParams['axes.prop_cycle'] = matplotlib.cycler(color=colors) 

from ada.geometry.airfoils.kulfan import Kulfan

PATH_TO_ADA = os.environ['PATH_TO_ADA']

dat_fls = os.listdir(PATH_TO_ADA + 'ada/geometry/airfoil_scraping/raw_airfoil_files/airfoiltools_airfoils')
dat_fls.sort()

for i in range(0,len(dat_fls)):
    dtf = dat_fls[i]
    if 's8' in dtf:
        nm = dtf[0:-4]
        afl = Kulfan()
        afl.fit2file(PATH_TO_ADA + 'ada/geometry/airfoil_scraping/raw_airfoil_files/airfoiltools_airfoils/' + dtf)
        afl.write2file(PATH_TO_ADA + 'ada/geometry/airfoil_files/' + nm.lower() + '.dat')
