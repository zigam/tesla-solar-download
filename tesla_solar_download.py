"""
Copyright 2023 Ziga Mahkovec

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import argparse
import csv
import os
import time
from datetime import datetime, timedelta

import pytz
import teslapy
from dateutil.parser import parse


def _get_csv_name(date, site_id):
    str_date = date.strftime('%Y-%m-%d')
    return f'download/{site_id}/{str_date}.csv'


def _write_csv(timeseries, date, site_id):
    if not timeseries:
        raise ValueError(f'No timeseries for {date}')

    csv_filename = _get_csv_name(date, site_id)
    os.makedirs(os.path.dirname(csv_filename), exist_ok=True)
    fieldnames = list(timeseries[0].keys()) + ['load_power']
    with open(csv_filename, 'w') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for ts in timeseries:
            ts['timestamp'] = parse(ts['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            ts['load_power'] = (
                ts['solar_power']
                + ts['battery_power']
                + ts['grid_power']
                + ts['generator_power']
            )
            writer.writerow(ts)


def _download_day(tesla, site_id, timezone, date):
    start_date = date.replace(hour=0, minute=0, second=0).isoformat()
    end_date = date.replace(hour=23, minute=59, second=59).isoformat()
    response = tesla.api(
        'CALENDAR_HISTORY_DATA',
        path_vars={'site_id': site_id},
        kind='power',
        period='day',
        start_date=start_date,
        end_date=end_date,
        time_zone=timezone,
        fill_telemetry=0,
    )['response']

    _write_csv(response['time_series'], date, site_id)


def _download_data(tesla, site_id):
    site_config = tesla.api('SITE_CONFIG', path_vars={'site_id': site_id})['response']
    installation_date = parse(site_config['installation_date'])
    timezone = site_config['installation_time_zone']

    date = datetime.now(pytz.timezone(timezone)).replace(microsecond=0)
    while date > installation_date:
        if not os.path.exists(_get_csv_name(date, site_id)):
            print(date)
            _download_day(tesla, site_id, timezone, date)
            time.sleep(3)
        date -= timedelta(days=1)


def main():
    parser = argparse.ArgumentParser(
        description='Download Tesla Solar/Powerwall power data'
    )
    parser.add_argument(
        '--email', type=str, required=True, help='Tesla account email address'
    )
    args = parser.parse_args()

    tesla = teslapy.Tesla(args.email, retry=2, timeout=10)
    if not tesla.authorized:
        print('STEP 1: Log in to Tesla.  Open this page in your browser:\n')
        print(tesla.authorization_url())
        print()
        print(
            'After successful login, you will get a Page Not Found error.  That\'s expected.'
        )
        print('Just copy the url of that page and paste it here:')
        tesla.fetch_token(authorization_response=input('URL after authentication: '))
        print('\nSuccess!')

    for product in tesla.api('PRODUCT_LIST')['response']:
        resource_type = product.get('resource_type')
        if resource_type in ('battery', 'solar'):
            site_id = product['energy_site_id']
            print(f'Downloading data for {resource_type} site {site_id}')
            _download_data(tesla, product['energy_site_id'])


if __name__ == '__main__':
    main()