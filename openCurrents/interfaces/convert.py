_USDCUR = 20
_TR_FEE = 0.15

def usd_to_cur(amount_usd):
    return 1.0 / _USDCUR * amount_usd

def cur_to_usd(amount_cur, fee=False):
    if not fee:
        return _USDCUR * amount_cur
    else:
        return _USDCUR * (1 - _TR_FEE) * float(amount_cur)
