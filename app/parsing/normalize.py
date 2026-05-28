from app.utils.normalization import normalize_sector, normalize_stage


def normalize_investment_stages(stages):
    return normalize_stage(stages)


def normalize_sectors(sectors):
    return normalize_sector(sectors)
