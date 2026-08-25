import koreainvest_actions_hotfix as ki_hotfix
import pension_rates as pr


ki_hotfix.apply(pr)


if __name__ == "__main__":
    pr.main()
