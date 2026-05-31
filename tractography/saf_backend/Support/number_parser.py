
def number_parser(istr):
    if not istr:
        raise ValueError('number parsing error: input empty')
    if not isinstance(istr, str):
        raise ValueError('number parsing error: input must be a string')

    mpos = istr.find('M')
    kpos = istr.find('K')

    mval = 0.0
    kval = 0.0
    nval = 0.0

    if mpos != -1 and kpos != -1 and mpos > kpos:
        raise ValueError('number parsing error: M comes before K')

    def ocalc(mv, kv, nv):
        return mv * 10 ** 6 + kv * 10 ** 3 + nv

    if mpos != -1:
        if mpos == 0:
            raise ValueError('number parsing error: number of millions required')
        mval = float(istr[:mpos])
        if len(istr) == mpos + 1:
            return ocalc(mval, kval, nval)
    else:
        mpos = -1

    if kpos != -1:
        if kpos == 0 or kpos == mpos + 1:
            raise ValueError('number parsing error: number of thousands required')
        kval = float(istr[mpos + 1:kpos])
        if len(istr) == kpos + 1:
            return ocalc(mval, kval, nval)
    else:
        kpos = mpos

    nval = float(istr[kpos + 1:]) if kpos + 1 < len(istr) else 0.0
    return ocalc(mval, kval, nval)
