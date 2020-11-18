# hegic_analytics

### Install with `pip install .`

### Usage
```
import api
# select btw "options", "poolBalances", "bondingCurveEvents"
df = api.get_data("options")

which returns:

In [2]: df.head()
Out[2]: 
                                      account  amount  exercise_timestamp  ...  totalFee  type period_days
0  0x3b2cba3423199f73924ad609fa8eec504e1fac1f     1.0 2020-10-22 15:14:21  ...  0.079975  CALL          28
1  0xef764bac8a438e7e498c2e5fccf0f174c3e3f8db    50.0                 NaT  ...  3.998750   PUT          28
2  0x085af0cee7918f11e3983a9433b92a003153b155    50.0                 NaT  ...  0.501313  CALL          28
3  0x049261c9110499b6135b0cba5dc391104b8109ac    40.0                 NaT  ...  3.199000   PUT          28
4  0x049261c9110499b6135b0cba5dc391104b8109ac    40.0 2020-11-06 10:52:53  ...  3.199000  CALL          28
```