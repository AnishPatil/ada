import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
colors = ['#0065cc', '#e69f00', '#009e73', '#d55e00', '#56b4ff', '#fca7c7', '#ede13f', '#666666', '#000000']
matplotlib.rcParams['axes.prop_cycle'] = matplotlib.cycler(color=colors) 

from ada.geometry.airfoils.kulfan import Kulfan

PATH_TO_ADA = os.environ['PATH_TO_ADA']

txt_fls = os.listdir(PATH_TO_ADA + 'ada/geometry/airfoil_scraping/raw_airfoil_files/ffa_airfoils')
txt_fls.sort()

for i in range(0,len(txt_fls)):
    txf = txt_fls[i]
    if '.txt' in txf:
        nm = txf[0:-4]
        dta = np.loadtxt(PATH_TO_ADA + 'ada/geometry/airfoil_scraping/raw_airfoil_files/ffa_airfoils/' + txf)

        dta[:,0] -= dta[0,0]
        dta[:,0] /= dta[-1,0]
        dta[:,1] -= dta[0,1]
        dta[:,2] -= dta[0,2]

        coords = np.array([ np.append(list(reversed(dta[:,0])),dta[:,0]) , 
                            np.append(list(reversed(dta[:,1])),dta[:,2]) ])

        pstr = ''
        for j in range(0,len(coords[0])):
            pstr += '%.5f  %+.5f\n'%(coords[0][j],coords[1][j])
        pstr = pstr.replace('+',' ')
        pstr = pstr[0:-1]
        # print(pstr)
        
        f = open(PATH_TO_ADA + 'ada/geometry/airfoil_scraping/raw_airfoil_files/ffa_airfoils/' + nm + '.dat','w')
        f.write(pstr)
        f.close()

        afl = Kulfan()
        afl.fit2coordinates(coords[0],coords[1])
        afl.write2file(PATH_TO_ADA + 'ada/geometry/airfoil_files/' + nm.lower() + '.dat')

        # fig = plt.figure(figsize=(12,8))
        # plt.plot(coords[0],coords[1], color = colors[0])
        # plt.plot(afl.xcoordinates,afl.ycoordinates,'--',color = colors[1])
        # plt.grid(1)
        # plt.title(nm)
        # plt.axis('equal')




    
    