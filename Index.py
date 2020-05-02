"""
Data fetch & preprocessing script
for Statewide Temperature Index
visualization.
"""
# pylint: disable=C0103,E0401


import csv
import os
import sys
import datetime
import ssl
from urllib.request import urlopen
import numpy as np
import scipy.stats

# TODO rename this
localPath = "./data/"

# Bypass SSL certification check for HTTPS
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    # Legacy Python that doesn't verify HTTPS certificates by default
    pass
else:
    # Handle target environment that doesn't support HTTPS verification
    ssl._create_default_https_context = _create_unverified_https_context


# Create a list of the dates used for analysis. The end date should extend into the future.
# TODO make this usually extend 1 year back?
stdate = datetime.date(2019, 6, 1)
enddate = datetime.date.today() + datetime.timedelta(days=-1)

numdays = (enddate - stdate).days + 1

# TODO figure out why this is different from enddate
today = datetime.date.today() + datetime.timedelta(days=-1)

# TODO bake these into the above
s1 = stdate.strftime("%Y-%m-%d")
s2 = enddate.strftime("%Y-%m-%d")
s3 = today.strftime("%Y-%m-%d")

# TODO what is this code doing?
# I think it's making an array of dates.
# This could be done better in Pandas.
List_of_Dates = np.empty(numdays, dtype=np.dtype("U10"))
List_of_Dates[0] = stdate.strftime("%Y-%m-%d")
for aa in range(0, numdays - 1):
    tempdate = stdate + datetime.timedelta(days=aa + 1)
    List_of_Dates[aa + 1] = tempdate.strftime("%Y-%m-%d")


##
# This next section downloads all the ACIS data and writes one line for each
# day's record for each station.


# Get the list of stations and their USW codes
Station_USW = np.empty(25, dtype=np.dtype("U11"))
Station_Name = np.empty(25, dtype=np.dtype("U99"))
Station_ICAO = np.empty(25, dtype=np.dtype("U4"))
Station_Weight = np.empty(25, dtype=float)

datastring = "Date,USW,Name,Label1,Average,Label2,Normal,Label3,Depart SD,Weight\n"

lastdatestring = "USW,Name,SD\n"


# TODO It looks like this is kind of building
# a table-like structure as well as grabbing
# API data then doing adjustments.  Let's split this up, because it
# looks like `pandas.read_csv()` will do most
# of the work on that front.
# Fundamentally, it looks like this code is creating
# a new data table of station info.
with open("./StationsList.txt") as csv_station_name_file:
    csv_reader1 = csv.reader(csv_station_name_file, delimiter=",")
    station_count = 0  # this is incremented when a new station is encountered
    for row1 in csv_reader1:
        Station_USW[station_count] = row1[0]
        Station_Name[station_count] = row1[1]
        Station_ICAO[station_count] = row1[2]
        Station_Weight[station_count] = row1[3]
        # print(Station_USW[station_count]+"   "+Station_Name[station_count])
        station_URL = (
            "http://data.rcc-acis.org/StnData?sid="
            + row1[0]
            + "&sdate="
            + s1
            + "&edate="
            + s2
            + "&elems=1,2&output=csv"
        )
        response = urlopen(station_URL)
        html = response.read().decode("utf8")
        html_list = html.splitlines()
        del html_list[0]
        for x in html_list:
            if len(x) > 10:
                today_year = int(x[0:4])
                today_month = int(x[5:7])
                today_day = int(x[8:10])
                xx = x.split(",")
                # TODO This is omitting some data
                # from the ACIS results, if both
                # values are missing.
                # print(xx)
                if (
                    xx[1] != "M" and xx[2] != "M"
                ):  # look for entries where a valid max and min exist
                    today_max = xx[1]
                    today_min = xx[2]
                    today_ave = (int(today_max) + int(today_min)) / float(2.0)
                    if (
                        row1[2] == "PAOT" and today_year == 2019
                    ):  # adjustment for Kotzebue
                        if today_month == 5 and today_day >= 6:
                            today_ave = today_ave - 4
                        if today_month == 9 and today_day <= 9:
                            today_ave = today_ave - 4
                        if today_month >= 6 and today_month <= 8:
                            today_ave = today_ave - 4
                    if (
                        row1[2] == "PANC" and today_year >= 2017 and today_year <= 2018
                    ):  # adjustment for Anchorage
                        today_ave = today_ave - 2.0
                    if (
                        row1[2] == "PANC" and today_year == 2016 and today_month == 12
                    ):  # adjustment for Anchorage
                        today_ave = today_ave - 2.0
                    if (
                        row1[2] == "PANC" and today_year == 2020 and today_month == 1
                    ):  # adjustment for Anchorage
                        today_ave = today_ave - 2.0
                    today_ave_weighted = float(today_ave) * float(row1[3])
                    # print(row1[1] + "," + x[0:10] + "," + today_max + "," + today_min)
                    with open("./StationsNormals.txt") as csv_normal_file:
                        csv_reader2 = csv.reader(csv_normal_file, delimiter=",")
                        for row2 in csv_reader2:
                            if (
                                row2[0] == row1[0]
                                and int(row2[2]) == int(today_month)
                                and int(row2[3]) == int(today_day)
                            ):
                                norm_ave = float(row2[6])
                                norm_sd = float(row2[9])
                                depart = float(today_ave) - float(norm_ave)
                                depart_sd = (
                                    float(today_ave) - float(norm_ave)
                                ) / float(norm_sd)
                                depart_sd_weighted = (
                                    (float(today_ave) - float(norm_ave))
                                    / float(norm_sd)
                                    * float(row1[3])
                                )
                    datastring = (
                        datastring
                        + x[0:10]
                        + ","
                        + row1[0]
                        + ","
                        + row1[1]
                        + ",Ave,"
                        + str(today_ave)
                        + ",Norm,"
                        + str(norm_ave)
                        + ",Depart SD,"
                        + str(round(depart_sd, 3))
                        + ",Weight,"
                        + str(row1[3])
                        + "\n"
                    )
                    # TODO is lastdate used at all?
                    if x[0:10] == s3:  # look for the last date
                        lastdatestring = (
                            lastdatestring
                            + row1[0]
                            + ","
                            + row1[1]
                            + ","
                            + str(round(depart_sd, 3))
                            + "\n"
                        )
        station_count += (
            1
        )  # increment the station count (e.g., Anchorage is first, Barrow is second, etc.)

# print("\n\n\n\n\n" + datastring)

exists = os.path.exists(localPath + "DailyData.txt")
if exists == True:
    os.remove(localPath + "DailyData.txt")
with open(localPath + "DailyData.txt", "w") as f:
    f.write(datastring)

# TODO is lastdate used anywhere?
exists = os.path.exists(localPath + "LastDayOnly.txt")
if exists == True:
    os.remove(localPath + "LastDayOnly.txt")
with open(localPath + "LastDayOnly.txt", "w") as f:
    f.write(lastdatestring)


sys.exit()

##
# Loop though List_of_Dates array and then open the DailyData.txt file and find matching dates


AveDailySD = np.empty(numdays, dtype=float)

summaryString = "Date,Ave SD,Num Stations,Daily Index,Daily Temp\n"

for bb in range(0, numdays):
    dateStr = List_of_Dates[bb]
    dailyAvg = float(0.0)
    dailySum = float(0.0)
    dailyTemp = float(0.0)
    dailyAvgTemp = float(0.0)
    dailyCount = 0
    with open(localPath + "DailyData.txt") as csv_daily_file:
        csv_reader3 = csv.reader(csv_daily_file, delimiter=",")
        for row3 in csv_reader3:
            if row3[0] == dateStr:
                dailyCount += 1
                dailySum += float(row3[8]) * float(row3[10])
                dailyTemp += (float(row3[4])) * float(row3[10])
                dailyAvg = dailySum / float(dailyCount)
                dailyAvgTemp = dailyTemp / float(dailyCount)
    if dailyCount > 0:
        ww = scipy.stats.norm(0, 0.71074).cdf(dailyAvg)
        if ww < 0.5:
            prob = round(0 - (20 * (0.5 - ww)), 3)
        if ww >= 0.5:
            prob = round(20 * (ww - 0.5), 3)
        print(
            dateStr
            + ","
            + str(round(dailyAvg, 3))
            + ","
            + str(dailyCount)
            + ","
            + str(prob)
        )
        summaryString = (
            summaryString
            + dateStr
            + ","
            + str(round(dailyAvg, 3))
            + ","
            + str(dailyCount)
            + ","
            + str(prob)
            + ","
            + str(round(dailyAvgTemp, 3))
            + "\n"
        )

exists = os.path.exists(localPath + "DailySummary.txt")
if exists == True:
    os.remove(localPath + "DailySummary.txt")

with open(localPath + "DailySummary.txt", "w") as f:
    f.write(summaryString)

##

theDates = []
theValues = []

with open(localPath + "DailySummary.txt") as csv_summary_file:
    csv_reader4 = csv.reader(csv_summary_file, delimiter=",")
    for row4 in csv_reader4:
        theDates.append(row4[0])
        theValues.append(row4[3])

del theDates[0]
del theValues[0]

theCount = len(theDates)


all_dates = np.empty(theCount, dtype=np.dtype("U10"))
all_vals = np.empty(theCount, dtype=float)
pos_vals = np.empty(theCount, dtype=float)
neg_vals = np.empty(theCount, dtype=float)


for yy in range(0, theCount):
    all_dates[yy] = theDates[yy]
    all_vals[yy] = float(theValues[yy])
    pos_vals[yy] = float(theValues[yy])
    neg_vals[yy] = float(theValues[yy])


for zz in range(0, theCount):
    if pos_vals[zz] < 0:
        pos_vals[zz] = np.nan
    if neg_vals[zz] > 0:
        neg_vals[zz] = np.nan


## Get MOS

curtime = datetime.datetime.now().hour + (datetime.datetime.now().minute / float(60))

MOS_URL = "https://www.nws.noaa.gov/mdl/forecast/text/state/AK.MRF.htm"
# MOS_URL = 'https://www.nws.noaa.gov/mdl/forecast/text/mrfmex00.txt'
# MOS_URL = 'https://www.nws.noaa.gov/mdl/forecast/text/mrfmex12.txt'
MOS_response = urlopen(MOS_URL)
MOS_html = str(MOS_response.read())
MOS_html_list = MOS_html.split("\n")
mosstring = ""
for x6 in MOS_html_list:
    mosstring = mosstring + x6 + "\n"
with open(localPath + "LatestMOS.txt", "w") as f:
    f.write(mosstring)

day1sum = float(0.0)
day2sum = float(0.0)
day3sum = float(0.0)
day4sum = float(0.0)
day5sum = float(0.0)
day6sum = float(0.0)
day7sum = float(0.0)

day1temp = float(0.0)
day2temp = float(0.0)
day3temp = float(0.0)
day4temp = float(0.0)
day5temp = float(0.0)
day6temp = float(0.0)
day7temp = float(0.0)

day1index = float(0.0)
day2index = float(0.0)
day3index = float(0.0)
day4index = float(0.0)
day5index = float(0.0)
day6index = float(0.0)
day7index = float(0.0)


MOShour = 99  # Initialize at something other than 0 or 12 so it passes the first check

checkline = 0
stationcounter = 0
for x5 in Station_ICAO:
    theWeight = Station_Weight[stationcounter]
    stationcounter += 1
    for x6 in MOS_html_list:
        if len(x6) > 40 and x6[1:5] == x5:  # This is the station header line
            MOShour = int(x6[39:41])
            MOSyear = int(x6[33:37])
            MOSmonth = int(x6[27:29])
            MOSday = int(x6[30:32])
            MOSdate = datetime.date(MOSyear, MOSmonth, MOSday)
            checkline = 0
        checkline += 1
        if MOShour < 99 and checkline == 4:
            onestr = x5 + "-->" + x6
            print(onestr)
            day1date = MOSdate + datetime.timedelta(days=1)
            day2date = MOSdate + datetime.timedelta(days=2)
            day3date = MOSdate + datetime.timedelta(days=3)
            day4date = MOSdate + datetime.timedelta(days=4)
            day5date = MOSdate + datetime.timedelta(days=5)
            day6date = MOSdate + datetime.timedelta(days=6)
            day7date = MOSdate + datetime.timedelta(days=7)
            if MOShour == 0:
                day1forecast = (int(onestr[16:19]) + int(onestr[20:23])) / float(2.0)
                day2forecast = (int(onestr[24:27]) + int(onestr[28:31])) / float(2.0)
                day3forecast = (int(onestr[32:35]) + int(onestr[36:39])) / float(2.0)
                day4forecast = (int(onestr[40:43]) + int(onestr[44:47])) / float(2.0)
                day5forecast = (int(onestr[48:51]) + int(onestr[52:55])) / float(2.0)
                day6forecast = (int(onestr[56:59]) + int(onestr[60:63])) / float(2.0)
                day7forecast = (int(onestr[64:67]) + int(onestr[68:71])) / float(2.0)
            if MOShour == 12:
                day1forecast = (int(onestr[12:15]) + int(onestr[16:19])) / float(2.0)
                day2forecast = (int(onestr[20:23]) + int(onestr[24:27])) / float(2.0)
                day3forecast = (int(onestr[28:31]) + int(onestr[32:35])) / float(2.0)
                day4forecast = (int(onestr[36:39]) + int(onestr[40:43])) / float(2.0)
                day5forecast = (int(onestr[44:47]) + int(onestr[48:51])) / float(2.0)
                day6forecast = (int(onestr[52:55]) + int(onestr[56:59])) / float(2.0)
                day7forecast = (int(onestr[60:63]) + int(onestr[64:67])) / float(2.0)
            with open(localPath + "StationsNormals.txt") as csv_normal_file:
                csv_reader6 = csv.reader(csv_normal_file, delimiter=",")
                for row6 in csv_reader6:
                    if (
                        row6[10] == x5
                        and int(row6[2]) == day1date.month
                        and int(row6[3]) == day1date.day
                    ):
                        day1_norm_ave = float(row6[6])
                        day1_norm_sd = float(row6[9])
                        day1temp = day1temp + (float(day1forecast * theWeight))
                        day1sum = day1sum + (
                            (
                                (float(day1forecast) - float(day1_norm_ave))
                                / float(day1_norm_sd)
                            )
                            * theWeight
                        )
                    if (
                        row6[10] == x5
                        and int(row6[2]) == day2date.month
                        and int(row6[3]) == day2date.day
                    ):
                        day2_norm_ave = float(row6[6])
                        day2_norm_sd = float(row6[9])
                        day2temp = day2temp + (float(day2forecast * theWeight))
                        day2sum = day2sum + (
                            (
                                (float(day2forecast) - float(day2_norm_ave))
                                / float(day2_norm_sd)
                            )
                            * theWeight
                        )
                    if (
                        row6[10] == x5
                        and int(row6[2]) == day3date.month
                        and int(row6[3]) == day3date.day
                    ):
                        day3_norm_ave = float(row6[6])
                        day3_norm_sd = float(row6[9])
                        day3temp = day3temp + (float(day3forecast * theWeight))
                        day3sum = day3sum + (
                            (
                                (float(day3forecast) - float(day3_norm_ave))
                                / float(day3_norm_sd)
                            )
                            * theWeight
                        )
                    if (
                        row6[10] == x5
                        and int(row6[2]) == day4date.month
                        and int(row6[3]) == day4date.day
                    ):
                        day4_norm_ave = float(row6[6])
                        day4_norm_sd = float(row6[9])
                        day4temp = day4temp + (float(day4forecast * theWeight))
                        day4sum = day4sum + (
                            (
                                (float(day4forecast) - float(day4_norm_ave))
                                / float(day4_norm_sd)
                            )
                            * theWeight
                        )
                    if (
                        row6[10] == x5
                        and int(row6[2]) == day5date.month
                        and int(row6[3]) == day5date.day
                    ):
                        day5_norm_ave = float(row6[6])
                        day5_norm_sd = float(row6[9])
                        day5temp = day5temp + (float(day5forecast * theWeight))
                        day5sum = day5sum + (
                            (
                                (float(day5forecast) - float(day5_norm_ave))
                                / float(day5_norm_sd)
                            )
                            * theWeight
                        )
                    if (
                        row6[10] == x5
                        and int(row6[2]) == day6date.month
                        and int(row6[3]) == day6date.day
                    ):
                        day6_norm_ave = float(row6[6])
                        day6_norm_sd = float(row6[9])
                        day6temp = day6temp + (float(day6forecast * theWeight))
                        day6sum = day6sum + (
                            (
                                (float(day6forecast) - float(day6_norm_ave))
                                / float(day6_norm_sd)
                            )
                            * theWeight
                        )
                    if (
                        row6[10] == x5
                        and int(row6[2]) == day7date.month
                        and int(row6[3]) == day7date.day
                    ):
                        day7_norm_ave = float(row6[6])
                        day7_norm_sd = float(row6[9])
                        day7temp = day7temp + (float(day7forecast * theWeight))
                        day7sum = day7sum + (
                            (
                                (float(day7forecast) - float(day7_norm_ave))
                                / float(day7_norm_sd)
                            )
                            * theWeight
                        )
            # print(x5+': '+str(day5date)+'--> Fct: '+str(day5forecast)+'  Norm: '+str(day5_norm_ave)+'   SD: '+str(day5_norm_sd))

day1sum = day1sum / float(25.0)
day2sum = day2sum / float(25.0)
day3sum = day3sum / float(25.0)
day4sum = day4sum / float(25.0)
day5sum = day5sum / float(25.0)
day6sum = day6sum / float(25.0)
day7sum = day7sum / float(25.0)

day1temp = day1temp / float(25.0)
day2temp = day2temp / float(25.0)
day3temp = day3temp / float(25.0)
day4temp = day4temp / float(25.0)
day5temp = day5temp / float(25.0)
day6temp = day6temp / float(25.0)
day7temp = day7temp / float(25.0)


ww1 = scipy.stats.norm(0, 0.71074).cdf(day1sum)
if ww1 < 0.5:
    prob1 = str(round(0 - (20 * (0.5 - ww1)), 3))
if ww1 >= 0.5:
    prob1 = "+" + str(round(20 * (ww1 - 0.5), 3))
ww2 = scipy.stats.norm(0, 0.71074).cdf(day2sum)
if ww2 < 0.5:
    prob2 = str(round(0 - (20 * (0.5 - ww2)), 3))
if ww2 >= 0.5:
    prob2 = "+" + str(round(20 * (ww2 - 0.5), 3))
ww3 = scipy.stats.norm(0, 0.71074).cdf(day3sum)
if ww3 < 0.5:
    prob3 = str(round(0 - (20 * (0.5 - ww3)), 3))
if ww3 >= 0.5:
    prob3 = "+" + str(round(20 * (ww3 - 0.5), 3))
ww4 = scipy.stats.norm(0, 0.71074).cdf(day4sum)
if ww4 < 0.5:
    prob4 = str(round(0 - (20 * (0.5 - ww4)), 3))
if ww4 >= 0.5:
    prob4 = "+" + str(round(20 * (ww4 - 0.5), 3))
ww5 = scipy.stats.norm(0, 0.71074).cdf(day5sum)
if ww5 < 0.5:
    prob5 = str(round(0 - (20 * (0.5 - ww5)), 3))
if ww5 >= 0.5:
    prob5 = "+" + str(round(20 * (ww5 - 0.5), 3))
ww6 = scipy.stats.norm(0, 0.71074).cdf(day6sum)
if ww6 < 0.5:
    prob6 = str(round(0 - (20 * (0.5 - ww6)), 3))
if ww6 >= 0.5:
    prob6 = "+" + str(round(20 * (ww6 - 0.5), 3))
ww7 = scipy.stats.norm(0, 0.71074).cdf(day7sum)
if ww7 < 0.5:
    prob7 = str(round(0 - (20 * (0.5 - ww7)), 3))
if ww7 >= 0.5:
    prob7 = "+" + str(round(20 * (ww7 - 0.5), 3))

mosplotstring = (
    day1date.strftime("%b %d")
    + ": "
    + str(prob1)
    + "\n\n"
    + day2date.strftime("%b %d")
    + ": "
    + str(prob2)
    + "\n\n"
    + day3date.strftime("%b %d")
    + ": "
    + str(prob3)
    + "\n\n"
    + day4date.strftime("%b %d")
    + ": "
    + str(prob4)
    + "\n\n"
    + day5date.strftime("%b %d")
    + ": "
    + str(prob5)
    + "\n\n"
    + day6date.strftime("%b %d")
    + ": "
    + str(prob6)
    + "\n\n"
    + day7date.strftime("%b %d")
    + ": "
    + str(prob7)
)
mostempstring = (
    day1date.strftime("%b %d")
    + ": "
    + str(day1temp)
    + "\n\n"
    + day2date.strftime("%b %d")
    + ": "
    + str(day2temp)
    + "\n\n"
    + day3date.strftime("%b %d")
    + ": "
    + str(day3temp)
    + "\n\n"
    + day4date.strftime("%b %d")
    + ": "
    + str(day4temp)
    + "\n\n"
    + day5date.strftime("%b %d")
    + ": "
    + str(day5temp)
    + "\n\n"
    + day6date.strftime("%b %d")
    + ": "
    + str(day6temp)
    + "\n\n"
    + day7date.strftime("%b %d")
    + ": "
    + str(day7temp)
)

if MOShour == 0:
    filestring = (
        "00_UTC_MOS_"
        + str(MOSyear)
        + "_"
        + "%02d" % (MOSmonth,)
        + "_"
        + "%02d" % (MOSday,)
        + ".txt"
    )
if MOShour == 12:
    filestring = (
        "12_UTC_MOS_"
        + str(MOSyear)
        + "_"
        + "%02d" % (MOSmonth,)
        + "_"
        + "%02d" % (MOSday,)
        + ".txt"
    )


newmosstring = "MOS Issue Date,Forecast Date,Index Value\n"
newmosstring = (
    newmosstring
    + MOSdate.strftime("%b %d, %Y")
    + ";"
    + day1date.strftime("%b %d, %Y")
    + ";"
    + str(prob1)
    + "\n"
)
newmosstring = (
    newmosstring
    + MOSdate.strftime("%b %d, %Y")
    + ";"
    + day2date.strftime("%b %d, %Y")
    + ";"
    + str(prob2)
    + "\n"
)
newmosstring = (
    newmosstring
    + MOSdate.strftime("%b %d, %Y")
    + ";"
    + day3date.strftime("%b %d, %Y")
    + ";"
    + str(prob3)
    + "\n"
)
newmosstring = (
    newmosstring
    + MOSdate.strftime("%b %d, %Y")
    + ";"
    + day4date.strftime("%b %d, %Y")
    + ";"
    + str(prob4)
    + "\n"
)
newmosstring = (
    newmosstring
    + MOSdate.strftime("%b %d, %Y")
    + ";"
    + day5date.strftime("%b %d, %Y")
    + ";"
    + str(prob5)
    + "\n"
)
newmosstring = (
    newmosstring
    + MOSdate.strftime("%b %d, %Y")
    + ";"
    + day6date.strftime("%b %d, %Y")
    + ";"
    + str(prob6)
    + "\n"
)
newmosstring = (
    newmosstring
    + MOSdate.strftime("%b %d, %Y")
    + ";"
    + day7date.strftime("%b %d, %Y")
    + ";"
    + str(prob7)
    + "\n"
)

with open("d:\\CS490\\Index\\MOS\\" + filestring, "w") as f:
    f.write(newmosstring)

##
# Compute 30-day running average
runningave = np.empty(numdays, dtype=float)
for ttt in range(30, numdays + 1):
    runningave[ttt - 1] = np.average(all_vals[ttt - 30 : ttt])
##

# Plot Section
# TODO: remove all this

# daystoplot = 90
# frequency = 3  # spacing of the x-axis ticks and labels

# subsetdates = np.empty(daystoplot, dtype=np.dtype("U10"))
# subsetdates = all_dates[0 - daystoplot :]

# subsetdates2 = np.empty(daystoplot, dtype=np.dtype("U10"))


# for zzz in range(0, len(subsetdates)):
#     tempdate = datetime.date(
#         int(subsetdates[zzz][0:4]),
#         int(subsetdates[zzz][5:7]),
#         int(subsetdates[zzz][8:10]),
#     )
#     subsetdates2[zzz] = tempdate.strftime("%b %d")


# subsetall = np.empty(daystoplot, dtype=float)
# subsetpos = np.empty(daystoplot, dtype=float)
# subsetneg = np.empty(daystoplot, dtype=float)
# subsetrunave = np.empty(daystoplot, dtype=float)


# subsetall = all_vals[0 - daystoplot :]
# subsetpos = pos_vals[0 - daystoplot :]
# subsetneg = neg_vals[0 - daystoplot :]
# subsetrunave = runningave[0 - daystoplot :]

# afont = {"fontname": "Arial"}

# objects = subsetall
# y_pos = np.arange(len(objects))
# y_pos_range = range(len(subsetdates2))

# plt.figure(figsize=(12.5, 7.8), facecolor="white")
# plt.title(
#     "Alaska Statewide Temperature Index: "
#     + str(subsetdates2[0])
#     + ", "
#     + subsetdates[0][0:4]
#     + ", to "
#     + str(subsetdates2[daystoplot - 1])
#     + ", "
#     + subsetdates[daystoplot - 1][0:4],
#     fontweight="bold",
#     fontsize="xx-large",
#     y=1.05,
#     **afont
# )


# plt.bar(
#     y_pos, subsetpos, color="r", edgecolor="none", width=0.75, alpha=0.8, align="center"
# )
# plt.bar(
#     y_pos, subsetneg, color="b", edgecolor="none", width=0.75, alpha=0.8, align="center"
# )


# plt.xticks(y_pos_range[::frequency], subsetdates2[::frequency], rotation=90)
# plt.yticks(np.arange(-10.0, 10.1, 1))
# plt.ylabel(
#     "<- Below Normal     Index     Above Normal ->",
#     weight="bold",
#     fontsize="large",
#     **afont
# )

# plt.plot(y_pos, subsetrunave, "-k", linewidth=3)

# plt.xlim(-1, daystoplot)
# plt.ylim(-10.1, 10.1)
# plt.grid(True)
# plt.subplots_adjust(left=0.07, right=0.85, top=0.90, bottom=0.28)

# im = image.imread("d:\\CS490\\Index\\Logo.png")
# plt.figimage(im, 15, 15, zorder=3)

# plt.text(
#     14.5,
#     -15,
#     "Index based on 1981-2010 daily normals and standard deviations of 25 stations. A value",
#     size=13,
#     **afont
# )
# plt.text(
#     14.5,
#     -16,
#     "of +1 means that the day is warmer than 10% of all Above Normal days. A value of +8 means",
#     size=13,
#     **afont
# )
# plt.text(
#     14.5,
#     -17,
#     "the day is warmer than 80% of all Above Normal days; and so on. The opposite is true of",
#     size=13,
#     **afont
# )
# plt.text(14.5, -18, "negative numbers. Data source: NCEI & ACIS.", size=13, **afont)
# plt.text(
#     50.5, -18, "30-day average shown as black line.", weight="bold", size=13, **afont
# )
# plt.text(94, -12, str(subsetdates2[daystoplot - 1]), weight="bold", size=17, **afont)
# plt.text(
#     98.5,
#     6,
#     str(MOShour) + " UTC MOS\nForecast",
#     horizontalalignment="center",
#     weight="bold",
#     size=16,
#     **afont
# )
# plt.text(92, -7, mosplotstring, size=15, **afont)


# # plt.show()

# plt.savefig(localPath + "OutputPlot.png")


# TODO: Remove all this
# Arcpy section

# from arcpy import env

# arcpy.env.workspace = r"D:\\CS490\\Index"
# mxd = arcpy.mapping.MapDocument(localPath + "Map.mxd")
# arcpy.mapping.ExportToPNG(mxd, localPath + "map.png", resolution=45)
# del mxd

# #
# # Imagemagick Section

# os.chdir("C:\\Program Files\\ImageMagick-7.0.8-Q16\\")
# os.system(
#     "magick.exe convert "
#     + localPath
#     + "map.png -resize 185x143 D:\\CS490\\Index\\map2.png"
# )
# os.system(
#     "magick.exe convert "
#     + localPath
#     + "OutputPlot.png "
#     + localPath
#     + "map2.png -geometry +1052+625 -composite D:\\CS490\\Index\\result.png"
# )
# os.system(
#     "magick.exe convert "
#     + localPath
#     + "result.png -bordercolor Black -border 1x1 "
#     + localPath
#     + "result2.png"
# )

# os.system(
#     "magick.exe convert "
#     + localPath
#     + "result2.png -bordercolor White -border 10x10 "
#     + localPath
#     + "plot90days.png"
# )
# os.chdir(localPath)
# os.system("del map.png")
# os.system("del map2.png")
# os.system("del OutputPlot.png")
# os.system("del result.png")

# if MOShour == 0:
#     filestring2 = (
#         "00_UTC_MOS_"
#         + str(MOSyear)
#         + "_"
#         + "%02d" % (MOSmonth,)
#         + "_"
#         + "%02d" % (MOSday,)
#         + ".png"
#     )
# if MOShour == 12:
#     filestring2 = (
#         "12_UTC_MOS_"
#         + str(MOSyear)
#         + "_"
#         + "%02d" % (MOSmonth,)
#         + "_"
#         + "%02d" % (MOSday,)
#         + ".png"
#     )

# os.system(
#     "magick.exe convert "
#     + localPath
#     + "result2.png -bordercolor White -border 10x10 "
#     + localPath
#     + "Maps\\"
#     + filestring2
# )
# os.system("del result2.png")

## TODO: REMOVE
## Upload to AWS
# import boto3

# s3 = boto3.client("s3")
# with open("plot90days.png", "rb") as f:
#     s3.upload_fileobj(
#         f,
#         "daily-alaska-climate-graphics",
#         "plot90days.png",
#         ExtraArgs={"ContentType": "image/png"},
#     )
#     s3.upload_fileobj(
#         f,
#         "daily-alaska-climate-graphics",
#         "Index_"
#         + str(MOSyear)
#         + "_"
#         + "%02d" % (MOSmonth,)
#         + "_"
#         + "%02d" % (MOSday,)
#         + ".png",
#         ExtraArgs={"ContentType": "image/png"},
#     )
