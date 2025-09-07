import os

PATH_TO_ADA = os.environ['PATH_TO_ADA']

# ============================================================
# UIUC airfoil database
# ============================================================
import requests
import time

urlTag_temp = "https://m-selig.ae.illinois.edu/ads/coord_updates/"
urlTag      = "https://m-selig.ae.illinois.edu/ads/coord/"

f = open(PATH_TO_ADA + "ada/geometry/airfoil_scraping/UIUC_database_index.txt",'r')
uiucDatabaseText = f.read()
f.close()
uiucDatabaseLines = uiucDatabaseText.split('\n')

foundSplit = False

ctr = 0
for ln in uiucDatabaseLines:
    if '# Above this line are in a different folder' in ln:
        foundSplit = True
    elif '.dat' in ln:
        ctr += 1
        ents = ln.split()
        if foundSplit:
            url = urlTag + ents[0]
        else:
            url = urlTag_temp + ents[0]
            
        print(str(ctr), " : ", len(uiucDatabaseLines), "   " ,url)
        time.sleep(0.5)
        
        
        response = requests.get(url)
        f = open('airfoil_scraping/uiuc_airfoils/'+ents[0],'w')
        f.write(response.content.decode())
        f.close()
    else:
        # skip if no dat file in the line
        pass
    
    
# ============================================================
# Supplement from airfoil tools for airfoils not in UIUC
# ============================================================
import requests
import time
from bs4 import BeautifulSoup
from urllib.request import urlopen

f = open(PATH_TO_ADA + "ada/geometry/airfoil_scraping/airfoiltools_database.txt",'r')
airfoiltoolsDatabaseText = f.read()
f.close()
airfoiltoolsDatabaseLines = airfoiltoolsDatabaseText.split('\n')

ctr = 0
for ln in airfoiltoolsDatabaseLines:
    ctr += 1
    ents = ln.split()
    if ents[0][-3:] != '-il':
        print(ents[0][0:-3])
        name = ents[0][0:-3]
        
        url = "http://www.airfoiltools.com/airfoil/details?airfoil=" + ents[0]
        page = urlopen(url)
        html = page.read().decode("utf-8")
        soup = BeautifulSoup(html, "html.parser")
        lines = str(soup).split('\n')
        
        datfileLines = []
        active = False
        for ln in lines:
            if active and '</' in ln:
                break

            if active:
                datfileLines.append(ln)

            if 'background-color:#ddd' in ln:
                active = True

        f = open('airfoil_scraping/airfoiltools_airfoils/'+name+'.dat','w')
        f.write('\n'.join(datfileLines))
        f.close()
        
        time.sleep(0.5)
        
    
# ============================================================
# Airfoils from bigfoil
# ============================================================
import time
from bs4 import BeautifulSoup
from urllib.request import urlopen

# this file is obtained by searching for 'a' in the search box then copying the html
f = open(PATH_TO_ADA + "airfoil_scraping/ada/geometry/airfoil_scraping/bigfoil_database.txt",'r')
bigfoilDatabaseText = f.read()
f.close()

ctr = 0
bigfoilDatabaseLines = bigfoilDatabaseText.split('\n')
for ln in bigfoilDatabaseLines:
    ctr += 1
    # print(ln)
    ents = ln.split('.com/')
    ents2 = ents[1].split('.php')
    ents3 = ents2[1].split('<')
    ky = ents2[0]
    nm = ents3[0][2:]
    url = 'https://www.bigfoil.com/D/' + ky + 'DAT.php'

    page = urlopen(url)
    html = page.read().decode("utf-8")
    soup = BeautifulSoup(html, "html.parser")
    lines = str(soup).split('\n')

    for ln2 in lines:
        if '.DAT' in ln2:
            ix=ln2.find('/DAT/')
            last_bit = ln2[ix+5:]
            ix2 = last_bit.find('.DAT')
            datfile_name = last_bit[0:ix2]

            url2 = 'https://www.bigfoil.com/DAT/' + datfile_name + '.DAT'

            response = requests.get(url2)
            f = open('bigfoil_airfoils/'+datfile_name.lower()+'.dat','w')
            f.write(response.content.decode())
            f.close()

            print(str(ctr), " : 6324  ", url2)

            time.sleep(0.5)
        