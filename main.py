#from watchmakers.load import *
#from watchmakers.sensitivity import findRate


import lib.argparser as ap
import lib.TMVAGui.GUIRun as tvag
import lib.utils.dbutils as du
import lib.utils.rateparser as rp
import lib.TMVAFactory as tf
import lib.make_signal_singles as ss
import lib.make_signal_pairs as sp
import lib.make_background_singles as bs
import lib.make_background_pairs as bp
import lib.utils.splash as s
import glob
import os, sys, time
import json
import subprocess

basepath = os.path.dirname(__file__)
mainpath = os.path.abspath(basepath)
configpath = os.path.abspath(os.path.join(basepath,"config"))
dbpath = os.path.abspath(os.path.join(basepath,"db"))
guipath = os.path.abspath(os.path.join(basepath,"lib","TMVAGui"))

args = ap.args

#args defining what files are used to run what kind of MVA
BUILD = args.BUILD
RUNTMVA = args.RUNTMVA
RUNGUI = args.RUNGUI
DEBUG = args.DEBUG
PAIRS=args.PAIRS
SINGLES=args.SINGLES
DATADIR=args.DATADIR
PC=args.PHOTOCOVERAGE
JNUM=args.JNUM
OUTDIR=args.OUTDIR+'/results_%i' % (JNUM)

#Specifications of tank used to calculate rates/choose MC files
SHIELDTHICK=args.SHIELDTHICK
TANKRADIUS=args.TANKRADIUS
HALFHEIGHT=args.HALFHEIGHT


#Cuts applied if value is not None
TIMETHRESH=args.TIMETHRESH
INTERDIST=args.INTERDIST
RADIUSCUT=args.RADIUSCUT
ZCUT=args.ZCUT

if not os.path.exists(OUTDIR):
    os.makedirs(OUTDIR)
if BUILD is True and os.path.exists(OUTDIR) is True:
    print("WARNING: YOU ARE BUILDING SIGNAL/BKG FILES TO AN EXISTING DIRECTORY.")
    print("EXISTANT DATA IN THE DIRECTORY WILL BE DELETED IF YOU PROCEED")
    time.sleep(2)

#TODO:
#  - Need to make the OUTDIR that everything will be saved to.
#  - Load the cuts configuration json.  Any modifications done on
#  - command line should be added into the dictionary.
#  - Add the OUTDIR component onto the outputfile names given to each make
#    signal/background function.
#  - Want an option to only run the TMVA on the OUTDIR, no making the files
#  -

if __name__ == '__main__':
    s.splash()
    if not BUILD and not RUNTMVA and not RUNGUI:
        print("run 'python main.py --help' for possible analyses\n")
        sys.exit(0)

    #FIXME: Have these as a toggle flag?  Or in config json? 
    MAXSIGNALEV = 100000
    MAXBKGEV = 10000000
    sout = "%s/signal.root" % (OUTDIR)
    bout = "%s/background.root" % (OUTDIR)
    mvaout = "%s/TMVA_output.root" % (OUTDIR)

	
    if BUILD is True:
        print("----USING WATCHMAKERS TO ESTIMATE SIG/BKG RATES------")
        #FIXME: I don't like this hardcoded at all...
        rate_command = ["python", "/usr/gapps/adg/geant4/rat_pac_and_dependency/watchmakers/watchmakers.py","--newVers","--findRate","--tankRadius",str(TANKRADIUS),\
                "--halfHeight",str(HALFHEIGHT),"--shieldThick",str(SHIELDTHICK),"-C",PC]
        subprocess.call(rate_command)
        ratefiles_inmain = glob.glob("%s/*%s.txt"%(mainpath,str(PC)))
        if len(ratefiles_inmain) > 1:
            print("WARNING: POSSIBLE RACE CONDITION WITH RATEFILES IF RUNNING MULTIPLE JOBS AT ONCE.\n" +\
                    "CONTACT TEAL ABOUT MODIFYING THE FINDRATE FUNCTION IN WATCHMAKERS TO RESOLVE THIS.") 
        for rf in ratefiles_inmain:
            moverate_command = ["mv","-f", rf,OUTDIR]
            subprocess.call(moverate_command)
        print("------ESTIMATED BACKGROUND RATES SAVED TO OUTPUT DIR-------")
        
        print("------OPENING BACKGROUND RATES FILE, BUILD RATE DICTIONARY------")
        ratefiles_inoutdir = glob.glob("%s/rate_*.txt"%(OUTDIR))
        with open(str(ratefiles_inoutdir[0]),"r") as f:
            rates = rp.ParseRateFile(f)

	print("------BUILDING SIGNAL AND BACKGROUND FILES------")
        time.sleep(2)

        print("----LOADING CUTS TO USE AS DEFINED IN CONFIG DIR----")
        with open("%s/%s" % (configpath,"cuts.json"),"r") as f:
            cutdict = json.load(f)
        
        print("---GETTING ALL AVAILABLE BACKGROUND FILES FROM DATADIR---")
        bkgrootfiles=[]
      
        Bkg_types = ["PMT","WaterVolume"]
        for btype in Bkg_types:
            type_candidates = glob.glob("%s/%s/*%s*" % (DATADIR,PC,btype))
            for candidate in type_candidates:
                if "CHAIN" in candidate:
                    bkgrootfiles.append(candidate)

        if DEBUG is True:
            print("BKGFILES BEING USED: " + str(bkgrootfiles))
        if len(bkgrootfiles) == 0:
            print("NO BACKGROUND FILES FOUND.  EXITING")
            sys.exit(1)
        print("BACKGROUND FILES ACQUIRED.")
 
        sigrootfiles=[]
        if PAIRS is True:
            print("GETTING PROMPT/DELAYED PAIR MC FOR SIGNAL TRAINING")
            sigrootfiles += glob.glob("%s/%s/*pn_ibd.root" % (DATADIR,PC))
        if SINGLES is not None:
            print("GETTING SINGLES SIGNAL FILE OF TYPE %s" % (SINGLES))
            if SINGLES=="neutron":
                suffix="_ibd_n"
            if SINGLES=="positron":
                suffix="_ibd_p"
            else:
                print("SINGLES TYPE GIVEN NOT SUPPORTED.  EXITING")
                sys.exit(1)
            sigrootfiles += glob.glob("%s/%s/*%s.root" % (DATADIR,PC,suffix))

        if DEBUG is True:
            print("SIGNAL FILES BEING USED: " + str(sigrootfiles))
        
        if len(bkgrootfiles) == 0:
            print("NO SIGNAL FILES FOUND.  EXITING")
        print("SIGNAL FILES ACQUIRED.")

        #Save configuration files for user reference
        files_used = {"SIGNAL": sigrootfiles, "BACKGROUND": bkgrootfiles}
        with open(OUTDIR+"/SB_files_used.json","w") as f:
            json.dump(files_used,f,sort_keys=True,indent=4)
	with open(OUTDIR+"/cuts_applied.json","w") as f:
            json.dump(cutdict,f,sort_keys=True,indent=4)


        #FIXME: We have to load in the rates and pass them as an object
        #Into the getSignal and getBackground functions.  Then, modify
        #These functions to fill their ProcSummarys with the fed in rates,
        #As well as efficiencies post-cuts given to the TMVA
        if SINGLES is not None:
            print("PREPARING SINGLE SIGNAL NTUPLE FILES NOW...")
            ss.getSignalSingles(ratedict=rates,cutdict=cutdict,
                    rootfiles=sigrootfiles,outfile=sout)
            print("SIGNAL FILES COMPLETE.  PREPARING SINGLE BKG. NTUPLES...") 
            bs.getBackgroundSingles(ratedict=rates,cutdict=cutdict,
                    rootfiles=bkgrootfiles,outfile=bout)
        if PAIRS is True:
            print("PREPARING PAIRED SIGNAL NTUPLE FILES NOW...")
            sp.getSignalPairs(ratedict=rates,cutdict=cutdict, 
                    rootfiles=sigrootfiles,outfile=sout,max_entries=MAXSIGNALEV)
            print("SIGNAL FILES COMPLETE.  PREPAIRING PAIR BKG. NTUPLES...")
            bp.getBackgroundPairs(ratedict=rates, cutdict=cutdict,
                    rootfiles=bkgrootfiles,outfile=bout,max_entries=MAXBKGEV)
        print("SIGNAL AND OUTPUT FILES SAVED TO %s" % OUTDIR)


    if RUNTMVA is True:
        print("LOADING VARIABLES TO USE AS DEFINED IN CONFIG DIR")
        with open("%s/%s" % (configpath,"variables.json"),"r") as f:
            varstouse = json.load(f)
        with open("%s/%s" % (dbpath,"WATCHMAKERS_variables.json"),"r") as f:
            variable_db = json.load(f)
        if PAIRS is True:
            vsdict = du.loadPairVariableDescriptions(varstouse["pairs"],
                            variable_db)
        else:
            vsdict = du.loadSinglesVariableDescriptions(varstouse["singles"],
                            variable_db)

        methoddict = {}
        print("LOADING METHODS TO USE AS DEFINED IN CONFIG DIR")
        with open("%s/%s" % (configpath,"methods.json"),"r") as f:
            methoddict = json.load(f)
        
        if DEBUG is True:
            print("VARIABLES BEING FED IN TO MVA: " + str(vsdict))
            print("METHODS BEING FED IN TO MVA: " + str(methoddict))
        print("RUNNING TMVA ON SIGNAL AND BACKGROUND FILES NOW...")
        mvaker = tf.TMVARunner(signalfile=sout, backgroundfile=bout,
                mdict=methoddict, varspedict=vsdict)
        mvaker.RunTMVA(outfile=mvaout,pairs=PAIRS)
        subprocess.call(["mv","-f","%s/weights"%(mainpath),OUTDIR])


    if RUNGUI is True:
        tvag.loadResultsInGui(GUIdir=guipath, resultfile=mvaout)

