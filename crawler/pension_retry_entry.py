import koreainvest_actions_hotfix as ki_hotfix
import pension_rates as pr


ki_hotfix.apply(pr)

import pension_retry_failed as retry


if __name__ == "__main__":
    retry.main()
