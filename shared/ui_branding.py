"""Compact, resolution-independent module branding."""

from pathlib import Path


def install_header_wordmark(owner):
    import qt

    existing = getattr(owner, '_headerWordmark', None)
    path = Path(owner.resourcePath('Icons/SlicerDSpace-wordmark.svg'))
    artwork = path.read_bytes()
    # Transparent QFrames may report a black Window palette on a light parent.
    # Follow the effective heading text colour instead of that background role.
    owner.ui.headlineLabel.ensurePolished()
    foreground = owner.ui.headlineLabel.palette.color(qt.QPalette.WindowText)
    if foreground.lightness() > 128:
        artwork = artwork.replace(b'fill="#000000"', b'fill="#f5f3ee"')
    wordmark = existing if existing is not None else qt.QLabel(owner.ui.headerFrame)
    wordmark.setObjectName('slicerDSpaceHeaderWordmark')
    # Qt's SVG image plugin is available even when PythonQt does not wrap QtSvg.
    pixmap = qt.QPixmap()
    if not pixmap.loadFromData(qt.QByteArray(artwork), 'SVG'):
        raise ValueError('Cannot decode the packaged SlicerDSpace wordmark')
    pixmap = pixmap.scaled(664, 120, qt.Qt.KeepAspectRatio, qt.Qt.SmoothTransformation)
    pixmap.setDevicePixelRatio(4.0)
    wordmark.setPixmap(pixmap)
    wordmark.setFixedSize(166, 30)
    wordmark.setAccessibleName('SlicerDSpace')
    wordmark.setToolTip('SlicerDSpace')
    owner.ui.logoLabel.hide()
    owner.ui.headerTextWidget.hide()
    if existing is None:
        owner.ui.headerLayout.insertWidget(0, wordmark)
        owner.ui.headerLayout.insertStretch(1, 1)
    owner._headerWordmark = wordmark
    return wordmark
