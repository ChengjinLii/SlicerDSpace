"""Tiny complete ASCII VTP geometry for integration tests, not scientific data."""


def vtp_lines(count):
    points = " ".join("0 0 0 1 2 3" for _ in range(count))
    indices = " ".join(str(i) for i in range(count * 2))
    offsets = " ".join(str(2 * (i + 1)) for i in range(count))
    return (
        '<VTKFile type="PolyData" version="0.1" byte_order="LittleEndian"><PolyData>'
        f'<Piece NumberOfPoints="{count * 2}" NumberOfLines="{count}" '
        'NumberOfVerts="0" NumberOfStrips="0" NumberOfPolys="0">'
        '<Points><DataArray type="Float64" NumberOfComponents="3" format="ascii">'
        f'{points}</DataArray></Points><Lines>'
        f'<DataArray type="Int64" Name="connectivity" format="ascii">{indices}</DataArray>'
        f'<DataArray type="Int64" Name="offsets" format="ascii">{offsets}</DataArray>'
        '</Lines></Piece></PolyData></VTKFile>'
    )
