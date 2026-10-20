"""Executa o .ino real com IO substituido. Requer g++ no PATH."""
from pathlib import Path
import subprocess
import tempfile

base=Path(__file__).resolve().parent
names='local_ramp remote_jog jog_expiry link_expiry auto_profile north_nearest limited_wrap inversion physical_priority both_buttons electronic_limits sensor_fault stall_fault max_time stop_local_latch invalid_commands telemetry speed_limits speed_reduce_moving speed_increase_moving speed_persistence speed_power_loss speed_menu moving_both_not_menu menu_sensor_fault'.split()
with tempfile.TemporaryDirectory() as folder:
    exe=Path(folder)/'rotor_test'
    subprocess.run(['g++','-std=c++11','-Wall','-Wextra','-I',str(base/'stubs'),str(base/'test_firmware.cpp'),'-o',str(exe)],check=True)
    for name in names:subprocess.run([str(exe),name],check=True)
print(f'{len(names)} cenarios de firmware aprovados.')
