from kcpl import kcpl
from kcwater import kcwater
from os import getenv
import pytz
from requests import ConnectTimeout
from datetime import datetime

from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS


def get_credentials():
    kcpl_user = getenv('KCPL_USERNAME')
    kcpl_pass = getenv('KCPL_PASSWORD')
    kch2o_user = getenv('KCWATER_USERNAME')
    kch2o_pass = getenv('KCWATER_PASSWORD')
    if not (kcpl_user and kcpl_pass and kch2o_user and kch2o_pass):
        raise Exception("no kcpl/kcwater credentials")
    return {
        "kcpl": {
            "username": kcpl_user,
            "password": kcpl_pass
        },
        "kcwater": {
            "username": kch2o_user,
            "password": kch2o_pass
        }
    }


def send_data(points, bucket="utilities/autogen"):
    """Writes data to influxdb client in env properties."""
    client = InfluxDBClient.from_env_properties()
    # client = InfluxDBClient(url=getenv("INFLUXDB_V2_URL"), org=getenv(
    #     "INFLUXDB_V2_ORG"), token=getenv("INFLUXDB_V2_TOKEN"))
    write_api = client.write_api(write_options=SYNCHRONOUS)

    for i in points:
        write_api.write(bucket, 'patrickjmcd', i)
        print("Wrote {}".format(i._name))


def convert_water_usage(d):
    if d['billedCharge']:
        d['billedCharge'] = float(d['billedCharge'])
    if d['billedConsumption']:
        d['billedConsumption'] = float(d['billedConsumption'])
    d['gallonsConsumption'] = float(d['gallonsConsumption'])
    d['rawConsumption'] = float(d['rawConsumption'])
    d['scaledRead'] = float(d['scaledRead'])
    return d


def main():

    creds = get_credentials()
    points = []

    try:
        kcpl_client = kcpl.KCPL(
            creds['kcpl']['username'], creds['kcpl']['password'])

        kcpl_client.login()
        kcpl_data = kcpl_client.getUsage()
        print("Last energy usage data: " + str(kcpl_data[-2]))
        # End your session by logging out
        kcpl_client.logout()

        kcpl_points = [
            {
                'measurement': 'energy_usage',
                'fields': kcpl_data[-2],
                'time': kcpl_data[-2]['billDate']
            }
        ]
        # write_to_influxdb(influx_client, influx_db, kcpl_points)
    except Exception as e:
        print("Unable to get kcpl data")
        print(e)

    try:
        kcwater_client = kcwater.KCWater(
            creds['kcwater']['username'], creds['kcwater']['password'])

        kcwater_client.login()
        kcwater_data = kcwater_client.get_usage_daily()
        print("Last water usage data: " + str(kcwater_data[-1]))
        chargeDate = datetime.strptime(
            kcwater_data[-1]['chargeDateRaw'], "%d-%b-%Y").replace(tzinfo=pytz.timezone("America/Chicago"))
        kc_water_obj = convert_water_usage(kcwater_data[-1])
        kcwater_point = Point("water_usage")
        kcwater_point.field("gallonsConsumption",
                            kc_water_obj["gallonsConsumption"])
        kcwater_point.field("billedConsumption",
                            kc_water_obj["billedConsumption"])
        kcwater_point.field("rawConsumption", kc_water_obj["rawConsumption"])
        kcwater_point.field("scaledRead", kc_water_obj["scaledRead"])
        kcwater_point.time(chargeDate)

        print(chargeDate)

        points.append(kcwater_point)

    except Exception as e:
        print("Unable to get kcwater data")
        print(e)

    send_data(points)


def backfill(days=30):

    creds = get_credentials()
    points = []

    try:
        for yr in [2018, 2019, 2020, 2021]:
            for mo in range(1, 13):
                kcwater_client = kcwater.KCWater(
                    creds['kcwater']['username'], creds['kcwater']['password'])

                kcwater_client.login()
                kcwater_data = kcwater_client.get_usage_daily(
                    date=datetime(yr, mo, 15))

                for d in kcwater_data:
                    print("water usage data: " + str(d))
                    chargeDate = datetime.strptime(
                        d['chargeDateRaw'], "%d-%b-%Y").replace(tzinfo=pytz.timezone("America/Chicago"))
                    kc_water_obj = convert_water_usage(d)
                    kcwater_point = Point("water_usage")
                    kcwater_point.field("gallonsConsumption",
                                        kc_water_obj["gallonsConsumption"])
                    kcwater_point.field("billedConsumption",
                                        kc_water_obj["billedConsumption"])
                    kcwater_point.field(
                        "rawConsumption", kc_water_obj["rawConsumption"])
                    kcwater_point.field(
                        "scaledRead", kc_water_obj["scaledRead"])
                    kcwater_point.time(chargeDate)

                    points.append(kcwater_point)

    except Exception as e:
        print("Unable to get kcwater data")
        print(e)

    # print(points)
    send_data(points)


if __name__ == "__main__":
    main()
    # backfill()
