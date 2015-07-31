#!/bin/bash

set -e

TESTS_DIR="tests"

dpkg-checkbuilddeps -d 'xvfb, python-mock, python-unittest2,
                       python3-aptdaemon.test, python-lxml, python-qt4'

if [ ! -e /var/lib/apt-xapian-index/index ]; then
    echo "please run sudo update-apt-xapian-index"
    exit 1
fi

# check if basic http access works
HTTP_URL=http://software-center.ubuntu.com
if ! curl -s $HTTP_URL >/dev/null; then
    echo "NEED curl and http access to $HTTP_URL"
    exit 1
fi

./setup.py build
# run with xvfb

XVFB_CMDLINE=""

# mvo 2012-11-05: disabled as this causes hangs in raring
#XVFB=$(which xvfb-run)
XVFB=""

if [ $XVFB ]; then
    XVFB_CMDLINE="$XVFB -a"
fi

PYTHON="$XVFB_CMDLINE python -m unittest"

# and record failures here
OUTPUT=$TESTS_DIR"/output"

FAILED=""
run_tests_for_dir() {
    for i in $(find $1 -maxdepth 1 -name 'test_*.py'); do
        TEST_NAME=$(basename $i | cut -d '.' -f 1)
        TEST_PREFIX=$(echo `dirname $i` | sed -e s'/\//./g')
        printf '%-50s' "Testing $TEST_NAME..."
        if ! $PYTHON -v -c -b $TEST_PREFIX.$TEST_NAME > $OUTPUT/$TEST_NAME.out 2>&1; then
            FAILED="$FAILED $TEST_NAME"
            echo "[ FAIL ]"
            # add .FAIL symlink to make finding the broken ones trivial
            (cd $OUTPUT ; ln -s $TEST_NAME.out $TEST_NAME.out.FAIL)
        else
            echo "[  OK  ]"
            rm -f ${OUTPUT}/$file.out;
        fi
    done
}

if [ "$1" = "--sso-gtk" ]; then
    # Run the SSO GTK+ suite
    $PYTHON discover -s softwarecenter/sso/
elif [ $# -gt 0 ]; then
    # run the requested tests if arguments were given,
    # otherwise run the whole suite
    # example of custom params (discover all the tests under the tests/gtk3 dir):

    # ./run-tests.sh discover -v -s tests/gtk3/

    # See http://docs.python.org/library/unittest.html#test-discovery
    # for more info.
    RUN_TESTS="$PYTHON $@"
    echo "Running the command: $RUN_TESTS"
    $RUN_TESTS
else
    # 2012-05-30, nessita: Ideally, we should be able to run the whole suite
    # using discovery, but there is too much interference between tests in
    # order to do so, so we need a new python process per test file.
    ##RUN_TESTS="$PYTHON discover -v -c -b"
    rm -rf $OUTPUT
    mkdir $OUTPUT
    run_tests_for_dir "$TESTS_DIR/gtk3"
    run_tests_for_dir $TESTS_DIR

    # gather the coverage data
    ##./gen-coverage-report.sh

    if [ -n "$FAILED" ]; then
        echo "FAILED: $FAILED"
        echo "Check ${OUTPUT}/ directory for the details"
        exit 1
    else
        echo "All OK!"
    fi
fi
./setup.py clean
