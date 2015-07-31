#! /bin/sh

set -e

COVERAGE_DIR="./tests/coverage_html"

# run for a single test if the argument is given
if [ $1 ]; then
    python-coverage run --parallel $1
fi

# combine the reports
python-coverage combine

if [ -d $COVERAGE_DIR ]; then
    rm -rf $COVERAGE_DIR
fi

# generate the coverage data 
OMIT="/usr/share/pyshared/*,*piston*,*test_"
python-coverage report --omit=$OMIT | tee $COVERAGE_DIR/coverage_summary | tail

python-coverage html --omit=$OMIT -d $COVERAGE_DIR
echo "see $COVERAGE_DIR/index.html for the coverage details"
