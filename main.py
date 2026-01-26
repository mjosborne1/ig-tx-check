import argparse
import os
import sys
from  getter import get_npm_packages
from tester import run_example_check, run_capability_test, run_valueset_binding_report
from utils import check_path, get_config
import logging
from datetime import datetime

def main():
    """
    Check terminology using the $validate-code operation on a single fhir IG npm package
    downloded by the getter function from simplifier.net ig registry
    Keyword arguments:
    rootdir -- Root data folder, where the report file goes
    config.json tells the download which package to download from simplifier.net
    and which errors/warnings can be safely ignored or checked manually.    
    """
    
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
    print(f"Run started: {now.isoformat(timespec='seconds')}")
    FORMAT='%(asctime)s %(lineno)d : %(message)s'
    logging.basicConfig(format=FORMAT, filename=os.path.join('logs',f'ig-tx-check-{ts}.log'),level=logging.INFO)
    logger.info('Started')
    config_file = os.path.join(os.getcwd(),'config','config.json')
    # Get the initial config
    conf = get_config(config_file,"init")[0]
    mode = conf["mode"] or "clean"
    endpoint = conf["endpoint"] 
    # First check that the tx server instance is up 
    http_stat = run_capability_test(endpoint)
    if http_stat != 200:
        logger.fatal(f'Capability test failed with status: {http_stat}')
        sys.exit(1)
    logger.info("Passed Capability test, continue on with other checks")

    # Get npm packages and serialise to local folder
    npm_path_list = get_npm_packages(mode, data_dir=args.rootdir, config_file=config_file)
    print('...npm packages done')

    # Run Example checks
    run_example_check(endpoint, config_file, npm_path_list, outdir)
    logger.info("Example checks completed")
    
    # Run ValueSet binding report
    run_valueset_binding_report(npm_path_list, outdir, config_file)
    logger.info("ValueSet binding report completed")

    # Run Example ValueSet membership checks against profile bindings
    try:
        from membership import run_example_valueset_membership_check
        run_example_valueset_membership_check(endpoint, config_file, npm_path_list, outdir)
        logger.info("Example ValueSet membership checks completed")
    except Exception as e:
        logger.warning(f"Skipping ValueSet membership checks due to error: {e}")
    
    end_time = datetime.now()
    print(f"Run finished: {end_time.isoformat(timespec='seconds')}")
    logger.info("Finished")

if __name__ == '__main__':
    main()