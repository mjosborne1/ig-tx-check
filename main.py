import argparse
import os
import sys
import getter
import tester
from utils import check_path, get_config
import logging
from datetime import datetime

def main():
    homedir=os.environ['HOME']
    parser = argparse.ArgumentParser()
    defaultpath=os.path.join(homedir,"data","ig-tx-check")

    logger = logging.getLogger(__name__)
    parser.add_argument("-r", "--rootdir", help="Root data folder", default=defaultpath)   
    args = parser.parse_args()
    ## Create the data path if it doesn't exist
    check_path(args.rootdir)

    # setup report output folder for html reports   
    outdir = os.path.join(args.rootdir,"reports")
    check_path(outdir)

    ## Setup logging
    now = datetime.now() # current date and time
    ts = now.strftime("%Y%m%d-%H%M%S")
    FORMAT='%(asctime)s %(lineno)d : %(message)s'
    logging.basicConfig(format=FORMAT, filename=os.path.join('logs',f'ig-tx-check-{ts}.log'),level=logging.INFO)
    logger.info('Started')
    config_file = os.path.join(os.getcwd(),'config','config.json')
    # Get the initial config
    conf = get_config(config_file,"init")[0]
    mode = conf["mode"] or "clean"
    endpoint = conf["endpoint"] 
    # First check that the tx server instance is up 
    http_stat = tester.run_capability_test(endpoint)
    if http_stat != "200":
        logger.fatal(f'Capability test failed with status: {http_stat}')
        sys.exit(1)
    logger.info("Passed Capability test, continue on with other checks")

    # Get npm packages and serialise to local folder
    npm_path_list = getter.get_npm_packages(mode, data_dir=args.rootdir, config_file=config_file)
    print('...npm packages done')

    # Run Example checks
    tester.run_example_check(endpoint, config_file, npm_path_list, outdir)
    logger.info("Finished")

if __name__ == '__main__':
    main()