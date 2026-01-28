 
class AllocationStrategy:

    @staticmethod
    def name():...

    @staticmethod
    def equity_allocation(horizon_months):...

    @staticmethod
    def fixed_income_allocation(horizon_months):...

class GlidePath(AllocationStrategy):

    @staticmethod
    def name():
        return "Glide Path"
    
    @staticmethod
    def equity_allocation(horizon_months):
        horizon_years = horizon_months/12
        equity_allocation = max(0, min(1, horizon_years / 15)) 
        return equity_allocation 
    
    @staticmethod
    def fixed_income_allocation(horizon_months):
        return 1 - GlidePath.equity_allocation(horizon_months)
    
class EquityOnly:

    @staticmethod
    def name():
        return "Equity Only"
    
    @staticmethod
    def equity_allocation(horizon_months):
        return 1 
    
    @staticmethod
    def fixed_income_allocation(horizon_months):
        return 0
