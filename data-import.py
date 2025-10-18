#!/usr/bin/env python3

import argparse
import colorsys
import pickle
import zipfile
import pandas as pd
import os
from dataclasses import dataclass
from math import exp, inf
from simplekml import Kml

class DistTracker:
    def __init__(self):
        self.counts = [0] * 5

    def record(self, value):
        self.counts[min(len(self.counts)-1, int(value * len(self.counts)))] += 1

def scf(v):
    return 1.194 * v - 0.1733


def sigmoid(x, l = 1, k = 10, a = 0.5):
  return l / (1 + exp(-k * (x - a)))


def make_color(b, tracker):
    BAD_OBSERVED = 100
    ratio = min(1,max(0, b/BAD_OBSERVED))
    smoothed = sigmoid(ratio)
    tracker.record(smoothed)

    green_h = 130 / 360
    red_h = 0
    h = green_h + smoothed * (red_h - green_h)

    r, g, b = colorsys.hsv_to_rgb(h, 1, 0.7)
    r = int(r * 256)
    g = int(g * 256)
    b = int(b * 256)
    return f"ff{b:02x}{g:02x}{r:02x}"

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
    parser.add_argument('--tracker', type=str, default="tracker.pickle", help='path to tracker file')

    args = parser.parse_args()

    merged_data = extract_specific_files(args.zip_file, args.filenames)

    try:
        with open(args.tracker, "rb") as f:
            tracker = pickle.load(f)
        print("using tracker", tracker.counts)
    except FileNotFoundError:
        print("making new tracker")
        tracker = DistTracker()

    kml = Kml()
    # fol = kml.newfolder(name=args.zip_file)
    min_bri = inf
    max_bri = -inf
    for segment in merged_data:
        if segment.start == segment.end:
            print("skipping segment with equal start and end")
            continue
        lin = kml.newlinestring(coords=[segment.start, segment.end])
        bri = segment.acc.abs().mean() * scf(segment.vel)
        min_bri = min(min_bri, bri)
        max_bri = max(max_bri, bri)
        lin.style.linestyle.color = make_color(bri, tracker)
        lin.style.linestyle.width = 20
    kml.save(args.zip_file + ".kml")
    print(f"{min_bri=} {max_bri=}")

    print("saving tracker", tracker.counts)
    with open(args.tracker, "wb") as f:
        pickle.dump(tracker, f)

if __name__ == '__main__':
    main()
