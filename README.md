test readme state # 1

we have now got a PH. three candles with the middle candle high is higher than the LH and RH candels high.
1) we now need to calculate the FIB and place the entry limit orders.
a) The FIB is to be plotted from the most recent PL (low value) to the current PH (high value). as shown here.
b) we then need to calculate the size (net_size) and location (net_loc) of the limit orders to be placed. as see here with the black box. 
The calucation required to determine the net_size and net_loc is as follows:
b1) measure the % delta from the 1 FIB to the 0.236 FIB (in this case it is approx 8%). take this value and * by 0.375. meaning 8*0.375. 
This gives us 3. this means net_size = 3%. net location is centered around the 0.618FIB. therefore there is 1.5% net above and 1.5% net below the 0.618 FIB. 
now we know the net_size and net_location we need to determine the entry limit order size and locations. (user input number of limit orders at the start of 
the script, as well as balance and risk) with these variables we can now determine how many limits order need to be placed, as well as there size 
(balance  * risk spread over the number of limit orders. so that if all limit orders get filled and then price hits SL the damage to the account is only the 
risked portion)