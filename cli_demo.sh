#!/bin/bash
# AliExpress CLI Demo Script
# Shows the main ways to use the CLI tool

echo "🚀 AliExpress CLI Scraper - Quick Demo"
echo "====================================="
echo

# Set up variables  
PRODUCT_ID="3256809096800275"
COOKIE="_ga_save=yes; _ga=GA1.1.193409037.1753918991; cna=VdAXIS7eczACAUwgf8nvgNcn; aep_common_f=QpW8TzovzJ9W2jAB0DWPQ3x3fGijspl3I9/m1i702JK6Oj0HhMbXmQ==; x_router_us_f=x_alimid=6201491651; xman_us_f=zero_order=y&x_locale=en_US&x_l=0&x_user=PH|ae509486|user|ifm|6201491651&x_lid=ph1424156633tftae&x_c_chg=1&x_c_synced=1&acs_rt=1b30c08e93b84668bac6ea9a4e750a45&intl_locale=en_US; xman_us_t=ctoken=1cvlvubt3546n&l_source=aliexpress&x_user=Cs3DwpMc3jatzq5S9Jpqsf8wCx7yTJX2r7j0IasZfhM=&x_lid=ph1424156633tftae&sign=y&rmb_pp=hjukneyckf@gmail.com; xman_t=4ZmfVRKkBpQpt7lkPzh7rEH3O/TUPNwyNGRCsdupucP17RWA5WicCrAtactu1GyhbS8F5u/AjMwrFBbRzT5atV1ei7H1eNBGLSLqMSfnRPZJWvoalC8nyGhE/jJbpXvvitcKyH8WiI6uFr1HneD3zo7A8XLPOxgjr61hY7D0dYyvSQ0vvlwwtHrGQp3XHT6NduxZYS1tJMAx3UMj+eZTuY46o7Q8w0b+k05luOpNUB40fLBMSs5LhOJ2jNcDRGc48kFIXP+sTW/LG4x8cZrLy6fpHjqgnpkdvyOz0Q9Qqf0yXwLWNUJZJu+3nziPkLp0AsS0KNpriMYPhSEbaatIqhxyEnZPOxWMNGO0tuPMRxqiQJfbzmhqAVFmpM1L2CM4pbp0Rulm150N7yac63ImLE0nTjPDmt7nYDoKgF5xpn/cCcs+PmA53r8gu12XL9U0OHxVc9qwEIkx/tVBye55jklLKCgQO3hIhHXtS2cNtXhwRO3L7cNy2WG04XXXene2lz3gfyTohjyT3mJCM8v0SKQXNWdDS6NwDTc0IsYUoYmQt1iQngNu4zoWlylo7y7trXOhorPHUF7bQ+qP2NwsqZRJZ6HmgxK4RcCoTiLFz2bwCzqut7mpno4FQe+oibZrGgJfd0h3Vny13Kvo8gmsNT6ULB6FIBNlP96ZbCRUZMhVQNp8caxwQdDNWoOEljJTXwuimQOeEi6qtv/ifgcEIw==; sgcookie=E100+IYao6ZGypRlD9ZfO9Is0osdOfw1VGCW0zuaoZkIr2rofkRsx0V8ujYxvyFJr3rtIjNUlun++W2pkiurJBrIBwGjocmmdFSJTjVQkKb1Bek=; acs_usuc_t=x_csrf=grf1844o6l2w&acs_rt=16f12492387b4c4cb8b9a529bf573e2d; intl_locale=en_US; aep_usuc_f=site=usa&province=922878890000000000&city=922878897869000000&c_tp=USD&ga_saved=yes&x_alimid=6201491651&isb=y&region=US&b_locale=en_US&ae_u_p_s=2; aep_history=keywords%5E%0Akeywords%09%0A%0Aproduct_selloffer%5E%0Aproduct_selloffer%093256807960751186%093256809184052984%093256808312024826%093256809044444846%093256806765335934%093256808564901873%093256809341584289%093256809096800275; _m_h5_tk=998976f5bda3f9183f14daa31cbc84be_1754918131358; _m_h5_tk_enc=09a3caf1680838650ed4db88004911eb; intl_common_forever=aD6a7tzk1jlXkWe3YDeXOUpMBc8El7DysL6hLUDFMF2Xj795IUfoOA==; xman_f=yOmghrC1AiZb0iJglJtsZisNAvb0pzjPCI6wYSmO306PaujtmUaiKujvu5gqiJ9ebFN4oFYkvHlTEsuGL7I5gWWMgWMx1LrEA2EvF35E4xKwUpus03c/7IO1Ti9vaW7aUZhHmcCmD6Y2CMu4nZ591RUJ1Ciyy5XYQ1OybWuheoypc1+37/nMs1g5Kr/+4sLmJ2gfbd23xCSSoDUs+wDY6dFOTRpspNPDg7n4m2oBs/lNMRZEjA8z4pcPeyFhosIpGV1ZpLZY2U2dBVejpyGDauWr73gLk9z1vAJiGEMTH140p7lw2tb+y0/MuF+Vknj6+KKczBqEvYepfHhtn4bzy9BIW8Ozxdn34BV3zHoPy1XVeHH+r428Ku8IJnkbZBm/H7y7O9YtySerN1LWmdoFa8yuSRMv+9Nh8IAcgMwdYLX3tjxjXfpqbXjMq73hS35m; isg=BM_PHYwT-19JmP8qM19lAdb5XmPZ9CMWQB3paOHdaj5EsO6y68fyZ7bjtugOyPuO; _baxia_sec_cookie_=%257B%2522lwrid%2522%253A%2522AgGYdfQLkW6qiTdSMhw1X38RnLl3%2522%252C%2522lwrtk%2522%253A%2522AAIEaJotkjxvTdYxlseJIG%252B9EDqRs8moPcFs2r20RriaVZQSoLWN1sk%253D%2522%252C%2522epssw%2522%253A%252210*7_5ss6aySB-yICssU7FetvrRmRicAau84FwCAss3UNxQtC3stWv9tVyaUGIQO-XQb-xeb-aYYPyBDX4fuCCNu3GYgtiCQRC0vSDnOOOYOZUHsssWt4rOXnlzxAsitBftOWOOXR88A6uuTz7qrzyC8rubB-bPjLyQ1NHCHdn8zs1s9lWYrz64BDiKoUu8mImhsWt6OzbusxwXHy3wQ_hTVjpAoAO96dcr0EFaJdtE6sFabsss6suS9aYnOsdsOObsbRDEbsYMbkFCy_nNtVuTByAcFpsT7OCrcMmnI66HqHfAMzyz_mX-wfE3tKJK3MrLfrmv%2522%257D"

echo "1️⃣ Basic Usage"
echo "Command: python cli.py --product-id $PRODUCT_ID --cookie \"[COOKIE]\""
echo
python cli.py --product-id "$PRODUCT_ID" --cookie "$COOKIE"
echo
echo "===================================="
echo

echo "2️⃣ JSON Output"  
echo "Command: python cli.py -p $PRODUCT_ID -c \"[COOKIE]\" --json | head -10"
echo
python cli.py -p "$PRODUCT_ID" -c "$COOKIE" --json | head -10
echo "... (truncated)"
echo
echo "===================================="
echo

echo "3️⃣ Verbose Output"
echo "Command: python cli.py -p $PRODUCT_ID -c \"[COOKIE]\" --verbose"
echo  
python cli.py -p "$PRODUCT_ID" -c "$COOKIE" --verbose
echo
echo "===================================="
echo

echo "✅ CLI Demo Complete!"
echo "🎯 Ready for production use!"
echo "� See CLI_README.md for full documentation"
