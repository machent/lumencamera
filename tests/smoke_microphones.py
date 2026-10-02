"""Discover two real PulseAudio test sources and open the chosen source."""
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

with tempfile.TemporaryDirectory(prefix='lumen-audio-test-') as temp:
    server = 'unix:' + temp + '/pulse.sock'
    os.environ['PULSE_SERVER'] = server
    command = ['pulseaudio', '--daemonize=no', '-n', '--exit-idle-time=-1',
               '--log-target=file:' + temp + '/pulse.log',
               '--load=module-native-protocol-unix socket=' + temp + '/pulse.sock auth-anonymous=1',
               '--load=module-null-sink sink_name=lumen_audio',
               '--load=module-remap-source master=lumen_audio.monitor source_name=lumen_mic_one source_properties=device.description=LumenTestMicOne',
               '--load=module-remap-source master=lumen_audio.monitor source_name=lumen_mic_two source_properties=device.description=LumenTestMicTwo']
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    pipeline = None
    try:
        deadline = time.monotonic() + 6
        while subprocess.run(['pactl', '-s', server, 'info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
            if process.poll() is not None or time.monotonic() > deadline:
                raise RuntimeError('Test audio server did not start: ' + Path(temp, 'pulse.log').read_text())
            time.sleep(0.05)
        from app import Gst, microphone_inventory, microphone_source
        devices = microphone_inventory()
        inputs = {item['name']: item for item in devices}
        assert 'LumenTestMicOne' in inputs and 'LumenTestMicTwo' in inputs, list(inputs)
        assert all(not item['id'].endswith('.monitor') for item in devices)
        assert inputs['LumenTestMicOne']['id'] != inputs['LumenTestMicTwo']['id']
        for display, source_name in [('LumenTestMicOne', 'lumen_mic_one'), ('LumenTestMicTwo', 'lumen_mic_two')]:
            source = microphone_source(inputs[display]['device'])
            assert source.get_property('device') == source_name
            pipeline = Gst.parse_launch('queue name=inputqueue ! audioconvert ! fakesink sync=false')
            pipeline.add(source)
            assert source.link(pipeline.get_by_name('inputqueue'))
            assert pipeline.set_state(Gst.State.PLAYING) != Gst.StateChangeReturn.FAILURE
            _, state, _ = pipeline.get_state(3 * Gst.SECOND)
            assert state == Gst.State.PLAYING
            pipeline.set_state(Gst.State.NULL)
            pipeline = None
        print('PASS: live audio-device discovery, monitor filtering and two selected PulseAudio inputs')
    finally:
        if pipeline is not None:
            pipeline.set_state(Gst.State.NULL)
        process.terminate()
        process.wait(timeout=5)
