#!/usr/bin/env python3

import argparse
import colorsys
import zipfile
import pandas as pd
import os
from dataclasses import dataclass
from math import inf
from simplekml import Kml

def scf(v):
    return 1.194 * v - 0.1733

def make_color(b):
    GOOD_OBSERVED = 10
    MAX_OBSERVED = 278
    green_h = 130
    red_h = 0
    ratio = min(1,max(0, b/MAX_OBSERVED))
    h = green_h + ratio * (red_h - green_h)
    r, g, b = colorsys.hsv_to_rgb(h / 360, 1, 0.7)
    r = int(r * 256)
    g = int(g * 256)
    b = int(b * 256)
    return f"{r:02x}{g:02x}{g:02x}ff"

lat_col = "Latitude (°)"
lon_col = "Longitude (°)"
time_col = "Time (s)"
vel_col = "Velocity (m/s)"
acc_col = "Linear Acceleration z (m/s^2)"

@dataclass
class Segment:
    start: tuple[float, float]
    end: tuple[float, float]
    vel: float
    acc: pd.Series

def extract_specific_files(zip_file_path, filenames_to_extract):
    sensor_dataframes = []

    with zipfile.ZipFile(zip_file_path, 'r') as z:
        # Create a temporary directory for extraction
        temp_dir = 'temp_extracted_files'
        os.makedirs(temp_dir, exist_ok=True)
        
        for filename in ['Linear Acceleration.csv']:
            try:
                z.extract(filename, path=temp_dir)
                csv_path = os.path.join(temp_dir, filename)
                acc_data = pd.read_csv(csv_path)
                
            except KeyError:
                print(f'File {filename} not found in the zip archive.')


        # Iterate over desired filenames and extract them if they exist in the zip
        for filename in ['Location.csv']:
            try:
                z.extract(filename, path=temp_dir)
                csv_path = os.path.join(temp_dir, filename)
                data = pd.read_csv(csv_path)
                
            except KeyError:
                print(f'File {filename} not found in the zip archive.')


        for i in range(len(data) - 1):
            start_row = data.iloc[i]
            end_row = data.iloc[i+1]
            yield Segment(
                start=(start_row[lon_col], start_row[lat_col]),
                end=(end_row[lon_col], end_row[lat_col]),
                vel=start_row[vel_col],
                acc=acc_data[(start_row[time_col] <= acc_data[time_col]) & (acc_data[time_col] < end_row[time_col])][acc_col],
            )

        # Clean up temporary files and directory
        for f in os.listdir(temp_dir):
            os.remove(os.path.join(temp_dir, f))
        os.rmdir(temp_dir)




    
def main():
    parser = argparse.ArgumentParser(description='Extract specific files from zip archive and return DataFrame.')
    parser.add_argument('--zip_file', type=str, help='Path to the zip file')
    parser.add_argument('--filenames', nargs=2, type=str, default=['Linear Acceleration.csv', 'Location.csv'], help='Names of the two files to extract from the zip archive')

    args = parser.parse_args()

    merged_data = extract_specific_files(args.zip_file, args.filenames)

    # Print or return the DataFrame
    kml = Kml()
    min_bri = inf
    max_bri = -inf
    for segment in merged_data:
        lin = kml.newlinestring(coords=[segment.start, segment.end])
        bri = segment.acc.abs().mean() * scf(segment.vel)
        min_bri = min(min_bri, bri)
        max_bri = max(max_bri, bri)
        lin.style.linestyle.color = make_color(bri)
        lin.style.linestyle.width = 10
    kml.save(args.zip_file + ".kml")
    print(f"{min_bri=} {max_bri=}")

if __name__ == '__main__':
    main()
