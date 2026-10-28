"""Controlled Qt log-insertion comparison against an immutable prior snapshot."""

import hashlib
import json
import os
from pathlib import Path
import runpy
import statistics
import time
import traceback
from types import SimpleNamespace

import qt
import slicer


def run():
    root = Path(os.environ['SLICERDSPACE_SMOKE_ROOT'])
    try:
        from shared.ui_status_log import append_log, configure_log_widget
        reference = Path(os.environ['SLICERDSPACE_LOG_REFERENCE'])
        original = runpy.run_path(str(reference))['append_log']
        functions = {'original': original, 'batched': append_log}
        widgets = {name: qt.QPlainTextEdit() for name in functions}
        owners = {}
        for name, widget in widgets.items():
            configure_log_widget(widget, line_limit=4000)
            owners[name] = SimpleNamespace(ui=SimpleNamespace(logPlainTextEdit=widget),
                _logLineLimit=4000, _lastProcessEventsAt=float('inf'), _trim_log_widget=lambda widget: None)
        edge_cases = ('', '\n', 'first\n\nlast', 'spaces  stay\tand <tags> & text',
                      '中文日志\nERROR: sample\n\nWARNING: sample')
        for payload in edge_cases:
            for name, function in functions.items():
                widgets[name].clear()
                function(owners[name], payload)
            assert str(widgets['original'].toPlainText()) == str(widgets['batched'].toPlainText()), repr(payload)
            assert widgets['original'].document().blockCount == widgets['batched'].document().blockCount
        rows = []
        for count in (500, 2000):
            payload = '\n'.join(('WARNING: ' if index % 13 == 0 else '') +
                                'line <' + str(index) + '> & value' for index in range(count))
            times = {name: [] for name in functions}
            for repeat in range(8):
                order = ('original', 'batched') if repeat % 2 == 0 else ('batched', 'original')
                for name in order:
                    widget = widgets[name]
                    widget.clear()
                    started = time.perf_counter()
                    functions[name](owners[name], payload)
                    elapsed = time.perf_counter() - started
                    if repeat:
                        times[name].append(elapsed)
                    assert str(widget.toPlainText()) == payload
                    assert widget.document().blockCount == count
            baseline, optimized = (statistics.median(times[name]) for name in ('original', 'batched'))
            rows.append({'lines': count, 'original_seconds': times['original'],
                         'batched_seconds': times['batched'], 'original_median': baseline,
                         'batched_median': optimized, 'speedup': baseline / optimized,
                         'plaintext_sha256': hashlib.sha256(payload.encode()).hexdigest(),
                         'plaintext_and_block_count_exact': True,
                         'original_insertions': count, 'batched_insertions': 1})
        for widget in widgets.values():
            widget.deleteLater()
        result = {'status': 'passed', 'rows': rows, 'edge_case_plaintext_exact': True,
                  'reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
                  'scope': 'Qt log insertion only, hidden widgets, processEvents excluded equally; not algorithm or workflow speedup'}
    except Exception:
        traceback.print_exc()
        result = {'status': 'failed', 'error': traceback.format_exc()}
    (root / 'log_batch.json').write_text(json.dumps(result, indent=2) + '\n')
    print('LOG_BATCH=' + json.dumps(result), flush=True)
    slicer.app.exit(0 if result['status'] == 'passed' else 2)


qt.QTimer.singleShot(5000, run)
