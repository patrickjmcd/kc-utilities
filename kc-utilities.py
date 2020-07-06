from kcpl import kcpl
from kcwater import kcwater
from os import getenv
import sys
from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError, InfluxDBServerError
from requests import ConnectTimeout, ConnectTimeout


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


def get_influx_client():
    """Grabs the influxdb setup and client."""
    influx_address = getenv('INFLUXDB_ADDRESS')
    influx_port = getenv('INFLUXDB_PORT') or 8086
    influx_port = int(influx_port)
    influx_database = getenv('INFLUXDB_DB') or "utilities"
    influx_user = getenv('INFLUXDB_USER')
    influx_password = getenv('INFLUXDB_PASSWORD')
    influx_ssl = bool(getenv('INFLUXDB_SSL'))
    influx_verify_ssl = bool(getenv('INFLUXDB_VERIFYSSL'))
    if not influx_address:
        raise Exception("no influxdb address")

    influx = InfluxDBClient(
        influx_address,
        influx_port,
        database=influx_database,
        ssl=influx_ssl,
        verify_ssl=influx_verify_ssl,
        username=influx_user,
        password=influx_password,
        timeout=5
    )
    try:
        print('Testing connection to InfluxDb using provided credentials')
        influx.get_list_users()  # TODO - Find better way to test connection and permissions
        print('Successful connection to InfluxDb')
    except (ConnectTimeout, InfluxDBClientError, ConnectionError) as e:
        if isinstance(e, ConnectTimeout):
            print(
                'Unable to connect to InfluxDB at the provided address (%s)', influx_address)
        elif e.code == 401:
            print(
                'Unable to connect to InfluxDB with provided credentials')
        else:
            print(
                'Failed to connect to InfluxDB for unknown reason')
            print(e)

        sys.exit(1)

    return [influx, influx_database]


def write_to_influxdb(client, influx_database, data):
    try:
        client.write_points(data)
    except (InfluxDBClientError, ConnectionError, InfluxDBServerError) as e:
        if hasattr(e, 'code') and e.code == 404:
            print(
                'Database %s Does Not Exist.  Attempting To Create', influx_database)
            client.create_database(influx_database)
            client.write_points(data)
            return

        print('Failed To Write To InfluxDB')
        print(e)

    print('Data written to InfluxDB')


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
    [influx_client, influx_db] = get_influx_client()
    creds = get_credentials()

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
        write_to_influxdb(influx_client, influx_db, kcpl_points)
    except Exception as e:
        print("Unable to get kcpl data")
        print(e)

    # try:
    kcwater_client = kcwater.KCWater(
        creds['kcwater']['username'], creds['kcwater']['password'])

    kcwater_client.login()
    kcwater_data = kcwater_client.get_usage_daily()
    print("Last water usage data: " + str(kcwater_data[-1]))
    chargeDate = kcwater_data[-1]['chargeDateRaw'] + "T00:00:00Z"
    kc_water_obj = convert_water_usage(kcwater_data[-1])
    kcwater_points = [
        {
            'measurement': 'water_usage',
            'fields': kc_water_obj,
            'time': chargeDate
        }
    ]
    write_to_influxdb(influx_client, influx_db, kcwater_points)
    # except Exception as e:
    #     print("Unable to get kcwater data")
    #     print(e)


if __name__ == "__main__":
    main()
