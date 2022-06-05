import argparse
from asitop.asitop import main

parser = argparse.ArgumentParser(
    description='asitop: Performance monitoring CLI tool for Apple Silicon')
parser.add_argument('--interval', type=int, default=1,
                    help='Display interval and sampling interval for powermetrics (seconds)')
parser.add_argument('--color', type=int, default=2,
                    help='Choose display color (0~8)')
parser.add_argument('--avg', type=int, default=30,
                    help='Interval for averaged values (seconds)')
parser.add_argument('--show_cores', type=bool, default=False,
                    help='Choose show cores mode')

powermetrics_process = main(parser.parse_args())
try:
    powermetrics_process.terminate()
    print("Successfully terminated powermetrics process")
except Exception as e:
    print(e)
    powermetrics_process.terminate()
    print("Successfully terminated powermetrics process")
