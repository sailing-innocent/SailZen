import datetime

start_date_literal = "2025-06-05"
start_date = datetime.datetime.strptime(start_date_literal, "%Y-%m-%d")

ten_days = datetime.timedelta(days=10)
end_date = start_date + ten_days
print(f"Start Date: {start_date_literal}, End Date: {end_date.strftime('%Y-%m-%d')}")
one_handred_days = datetime.timedelta(days=100)
end_date = start_date + one_handred_days
end_date_literal = end_date.strftime("%Y-%m-%d")
print(f"Start Date: {start_date_literal}, End Date: {end_date_literal}")
