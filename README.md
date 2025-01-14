### Installation Requirements
- Python3 and the ability to install modules using pip. This will be automatic through the requirements file.
- A file path for the output of the process, on Windows this might be C:\data\ig-tx-check\ 
  on Mac/Linux it will be `/home/user/data/ig-tx-check` or similar where `user` is your account name


### How to install this script 
   * `git clone https://github.com/mjosborne1/ig-tx-check.git`
   * `cd ig-tx-check`
   * `virtualenv .venv`
   * `source ./.venv/bin/activate`
   * `pip install -r requirements.txt`

### How to run the script
   * Update `./config/config.json` to match the name and version of the package to be checked e.g.  
   ```       
        "name" : "hl7.fhir.au.base",             // name of the package on simplifier.net
        "version" : "4.2.2-preview",             // version of the package
        "title" : "AU Base Implementation Guide" // human readable description to aid debugging etc...            
   ```
   * ensure the virtual environment is set `source ./.venv/bin/activate`
   * `python main.py --rootdir /path/to/data/folder`  rootdir defaults to $HOME/data/ig-tx-check
   ```
        ig-tx-check % python main.py -h
        usage: main.py [-h] [-r ROOTDIR]

        options:
        -h, --help            show this help message and exit
        -r ROOTDIR, --rootdir ROOTDIR
                                Root data folder
   ```    

### Output
   * Output is an html file in $rootdir/reports called `ExampleCodeSystemChecks.html`