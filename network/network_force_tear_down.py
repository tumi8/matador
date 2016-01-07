'''
Copyright 2015 Johannes Zirngibl

This file is part of MATAdOR.

MATAdOR is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

MATAdOR is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

Tests if a tunnel instance is still running and SIGKILL is necessary.
'''
import subprocess
import sys

try:
    TUNNEL_PID = subprocess.check_output('ps x -o "%r %c" |grep tunnel -m 1',
                                         shell=True).decode('utf-8').split(' ')[1]
except subprocess.CalledProcessError:
    sys.exit(0)

try:
    subprocess.check_call('kill -9 -'+TUNNEL_PID,
                          shell=True)
except subprocess.CalledProcessError:
    sys.exit(3)
