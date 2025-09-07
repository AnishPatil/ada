# Ada: The AI Design Assistant

Ada is an AI empowered design assistant, specifically targeted at aircraft deisgn.

Currently, a variety of airfoil design capabilities are included.

## Installation
Ada requires the timelimit package, which can be obtained from homebrew:
```shell
brew install timelimt
```
This is a work around for a known python bug where timeouts cannot be used when writing output to STDOUT.

Clone the repository

cd to the parent directory

```shell
pip install -e ada
```
Note that Ada manages a hidden folder in your home directory: `(Home)/.ada` that will be used for managing the UI and relevant data

You must also set the following environment variables:

```shell
export OPENAI_ORG="your-openai-organization"
export OPENAI_API_KEY="your-openai-key"
```

Note that Ada currently requires the use of GPT-4, or GPT-4-Turbo (the default).  In testing, the function calling ability of GPT-3.5-Turbo has been inadequate to correctly select from the extensive function library that ships with Ada.  You may choose to switch to GPT-3.5-Turbo to save money, but you do this at your own risk.

The RAG and LLM calls still use GPT-3.5-Turbo as this seems sufficient in most cases.   

You must also have xfoil installed on your machine and callable as `xfoil`

To start the UI, first enable permissions:
```shell
cd ada
chmod 777 startServer.py
```

then start the server:
```shell
./startServer.py
```


## A suggested first session

```
generate a naca2412 airfoil
create an xfoil analysis case
naca4616
switch to airfoil 1
set alpha to 4.0
run case
plot the forces on the airfoil
plot the boundary layer
plot the momentum defect
plot the shape parameter
la5055
run
generate xfoil standard plot
plot the shape parameter
modify alpha to be (-10,10,15)
modify Re to be [1e6,1e7,1e8]
switch to airfoil 1
run
clear data
select data 1
select data 3
deselect data 1
plot the airfoil polars
```

