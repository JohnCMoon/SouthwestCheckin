#!/bin/bash
set -o errexit

# Run this script to restart any "active" checkins that might have been killed
sw_dir="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
active="${sw_dir}/active_checkins.csv"
checkin="${sw_dir}/checkin.py"

# If there's no file, just exit
if [ ! -f "$active" ]; then
	exit 0
fi

# Read all active checkins and start them if they don't exist
while read -r line; do
	conf_n=$(printf "%s" "$line" | cut -d ',' -f 1)
	f_name=$(printf "%s" "$line" | cut -d ',' -f 2)
	l_name=$(printf "%s" "$line" | cut -d ',' -f 3)
	email=$(printf "%s" "$line" | cut -d ',' -f 4)

	# If no process exists with this confirmation number, skip it
	if ! pgrep -a -f "$conf_n" | grep -q -v "pgrep" > /dev/null 2>&1; then
		nohup python -u "$checkin" \
			"$conf_n" "$f_name" "$l_name" "$email" > /dev/null 2>&1 &
	fi
done < <(cut -d ',' -f 1-4 "$active" | uniq)
