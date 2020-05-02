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
import logging
from urllib.request import urlopen
import numpy as np
import pandas as pd
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


# Set up logging
DASH_LOG_LEVEL = os.getenv("DASH_LOG_LEVEL", default="info")
logging.basicConfig(level=getattr(logging, DASH_LOG_LEVEL.upper(), logging.INFO))


def preprocess_normals():
    """
    Read the StationNormals.txt file provided with the repo,
    and do some pre-processing that doesn't need to be done
    during each data run.
    """
    # TODO check in with Brian on where this file is from.

    def month_day_to_date(row):
        # This needs to be a leap year to ensure full range of days.
        return datetime.date(2020, row["Month"], row["Day"]).strftime("%Y-%m-%d")

    normals = pd.read_csv("StationsNormals.txt")
    normals = normals.assign(date=normals.apply(month_day_to_date, axis=1))
    normals = normals.drop(
        columns=[
            "Month",
            "Day",
            "StationID",
            "ICAO",
            "MaxTemp",
            "MinTemp",
            "MaxTempSD",
            "MinTempSD",
        ]
    )
    normals.to_csv("normals.csv")


def build_daily_data():
    """
    Download ACIS data, perform some basic cleaning.
    """

    stations = pd.read_csv("StationsList.txt", index_col=0)
    normals = pd.read_csv("./normals.csv", index_col=0)
    normals["date"] = pd.to_datetime(normals["date"])
    all_stations = pd.DataFrame()

    start_date = datetime.date(2019, 6, 1).strftime("%Y-%m-%d")
    end_date = (datetime.date.today() + datetime.timedelta(days=-1)).strftime(
        "%Y-%m-%d"
    )

    for index, row in stations.iterrows():
        logging.info("Processing %s (%s)", row["placename"], index)
        station_data_url = "http://data.rcc-acis.org/StnData?sid={}&sdate={}&edate={}&elems=1,2&output=csv".format(
            index, start_date, end_date
        )
        logging.debug("Fetching API endpoint: %s", station_data_url)

        # std = station data
        std = pd.read_csv(
            station_data_url,
            names=["date", "maxt", "mint"],
            parse_dates=True,
            skiprows=1,
        )

        std = std.loc[(std["maxt"] != "M") & (std["mint"] != "M")]  # drop missing

        std["date"] = pd.to_datetime(std["date"])
        std["maxt"] = std["maxt"].astype("float")
        std["mint"] = std["mint"].astype("float")
        # std = std.assign(doy=std["date"].dt.strftime("%j").astype("int"))
        std = std.assign(usw=index)  # add station
        std = std.assign(current_average=std[["maxt", "mint"]].mean(axis=1))  # average

        # Subset for current location
        nd = normals.loc[normals["StationName"] == index]

        # Make an all-2020 date column to join with normals data properly
        std = std.assign(key_date=std["date"].apply(lambda dt: dt.replace(year=2020)))
        jd = std.set_index("key_date").join(nd.set_index("date"))

        # Departure standard deviation (SD) =
        # (current average - normal average) / normal SD
        jd = jd.assign(
            depart_sd=((jd["current_average"] - jd["AveTemp"]) / jd["AveTempSD"]).round(
                3
            )
        )
        jd = jd.drop(columns=["StationName"])
        all_stations = all_stations.append(jd)

    all_stations.to_csv("./data/test-daily-averages.csv")


def build_daily_index(sd):
    """
    (not working yet!)
    TODO fixme
    """
    # Remove any missing rows.
    sd = sd.dropna()
    stations = pd.read_csv("StationsList.txt")

    daily_index = pd.DataFrame(columns=["date", "daily_index"])

    grouped = sd.groupby(["date"])
    for day, group in grouped:

        # Add weights.
        joined = group.set_index("usw").join(stations.set_index("usw"))
        weighted_departure_sd_daily_mean = (
            joined["depart_sd"] * joined["weight"]
        ).mean()
        count = joined.shape[0]

        ww = scipy.stats.norm(0, 0.71074).cdf(weighted_departure_sd_daily_mean)
        if ww < 0.5:
            prob = round(0 - (20 * (0.5 - ww)), 3)
        if ww >= 0.5:
            prob = round(20 * (ww - 0.5), 3)

        # Compute daily index.
        daily_index = daily_index.append(
            {
                "date": day,
                "count": count,
                "daily_index": prob,
            },
            ignore_index=True,
        )
    daily_index["count"] = daily_index["count"].astype("int")
    daily_index.to_csv("./data/test-daily-index.csv")
    print(daily_index)  # all wrong 🤣


def test_daily_index():
    """
    Make a diff of the files.
    """
    old = pd.read_csv("./data/Reference-DailySummary-May2.csv")
    new = pd.read_csv("./data/test-daily-index.csv", index_col=0)
    joined = old.set_index("Date").join(new.set_index("date"))
    joined = joined.assign(index_delta=abs(joined["Daily Index"] - joined["daily_index"]))
    joined = joined.assign(count_delta=abs(joined["Num Stations"] - joined["count"]))
    print(joined)
    joined.to_csv("./data/test-compare-deltas.csv")

# preprocess_normals()  # if needed to reprocess the station normals
# build_daily_data()  # if needed to refresh data from API
# test_data = pd.read_csv("./data/test-daily-averages.csv")
# build_daily_index(test_data)
test_daily_index()
sys.exit()


############### work in progress ends here.


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
