#!/bin/sh

__ScriptVersion="1"

#===  FUNCTION  ================================================================
#         NAME:  usage
#  DESCRIPTION:  Display usage information.
#===============================================================================
usage ()
{
    echo "Usage :  $0 [options] COMMAND

    This is script for makefile concrete commands.

    Commands:
    install     Install pip
    test        Test code and show coverage
    clean       Clean associated files

    Options:
    -h|help       Display this message
    -v|version    Display script version"

}    # ----------  end of function usage  ----------

#-----------------------------------------------------------------------
#  Handle command line arguments
#-----------------------------------------------------------------------

while getopts ":hv" opt
do
  case $opt in

    h|help     )  usage; exit 0   ;;

    v|version  )  echo "$0 -- Version $__ScriptVersion"; exit 0   ;;

    * )  echo -e "\n  Option does not exist : $OPTARG\n"
          usage; exit 1   ;;

  esac    # --- end of case ---
done

if [[ "$1" == "" ]]; then
    echo "Missing position parameter: COMMAND" 
    usage
    exit 1
fi

case $1 in
    install )
        pip install -r requirements.txt
        exit 0 ;;
    test )
        coverage run runtests.py
        coverage report -m
        exit 0 ;;
    clean )
        find . \( -name *.pyc -o -name __pycache__ -o -name .coverage -o -name *,cover\) -delete
        exit 0 ;;
    * ) echo "Invalid command: $1\nPlease use --help/-h to review usage."
        exit 1 ;;
esac
