_USDCUR = 10

def usd_to_cur(amount_usd):
    return 1.0 / _USDCUR * amount_usd

def cur_to_usd(amount_cur):
    return _USDCUR * amount_cur