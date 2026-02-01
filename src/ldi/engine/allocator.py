 
def clamp(n, min_n=0, max_n=1):
    return min(max_n, max(min_n, n))

class AllocationStrategy:

    @staticmethod
    def name():...

    @staticmethod
    def get_allocation(inputs):...

class GlidePath(AllocationStrategy):

    FUNDING_HEDGE_WEIGHT = .4
    TIME_HEDGE_WEIGHT = .6

    @staticmethod
    def name():
        return "Glide Path"
    
    @staticmethod
    def get_allocation(inputs):

        horizon_months = inputs.get("horizon_months")
        funding_ratio = inputs.get("funding_ratio")

        funding_hedge = clamp((funding_ratio - .7) / (1 - .7)) if funding_ratio != None else 0
        time_hedge = clamp(1 - horizon_months/(12*15))

        base_hedge = GlidePath.FUNDING_HEDGE_WEIGHT * funding_hedge + GlidePath.TIME_HEDGE_WEIGHT * time_hedge
    
        return {
            "us_equity_total_market": 0.7 * (1 - base_hedge),
            "intl_equity_developed": 0.3 * (1 - base_hedge),
            "us_nominal_treasury_long": 0.8 * base_hedge,
            "us_tips_long": 0.2 * base_hedge,
        }

