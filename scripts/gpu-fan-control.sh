#!/bin/bash
# gpu-fan-control — GPU-temperature-driven fan curve for R730 + NVIDIA.
#
# Reads max GPU temp every POLL seconds, maps it to a fan % via curve(), and
# applies it with iDRAC manual fan control (ipmitool raw 0x30 0x30). An exhaust
# sensor acts as a chassis-wide safety net for CPU-heavy load the GPU curve misses.
#
# FAILSAFE: on ANY exit (stop/crash/kill) or on loss of GPU telemetry it hands
# control back to iDRAC automatic mode (0x30 0x30 0x01 0x01). With
# ThirdPartyPCIFanResponse=Disabled, iDRAC-auto is the measured-safe ~4,080 RPM
# baseline (72B load = 63 C, single-card compute = 81 C — both in spec), so
# failing over to auto is safe, not a meltdown.
#
# Prereq: ThirdPartyPCIFanResponse=Disabled (else auto mode is the loud 14,800 ramp).
set -u

POLL=5                 # seconds between polls
FLOOR=15               # minimum fan % (≈ quiet auto baseline; measured CPU-safe)
EXHAUST_TRIP=45        # exhaust C that forces >=70% (chassis-wide safety net)
MAXFAILS=3             # consecutive nvidia-smi failures -> give up (stay AUTO)

log(){ echo "$(date '+%F %T') $*"; }

fan_auto(){   ipmitool raw 0x30 0x30 0x01 0x01 >/dev/null 2>&1; }
fan_manual(){ ipmitool raw 0x30 0x30 0x01 0x00 >/dev/null 2>&1; }
fan_set(){    ipmitool raw 0x30 0x30 0x02 0xff "$(printf '0x%02x' "$1")" >/dev/null 2>&1; }

# Whatever happens, give iDRAC back control (safe measured baseline).
# Clear traps first to avoid re-entry, then exit cleanly so `systemctl stop` -> inactive.
cleanup(){ trap - EXIT INT TERM; fan_auto; log "exit -> fans handed back to iDRAC AUTO"; exit 0; }
trap cleanup EXIT INT TERM

curve(){ # $1 = temp C -> fan %
	local t=$1
	if   [ "$t" -lt 50 ]; then echo 15
	elif [ "$t" -lt 60 ]; then echo 25
	elif [ "$t" -lt 70 ]; then echo 35
	elif [ "$t" -lt 75 ]; then echo 45
	elif [ "$t" -lt 80 ]; then echo 60
	elif [ "$t" -lt 85 ]; then echo 80
	else echo 100
	fi
}

# Ensure iDRAC's third-party PCIe fan response is Disabled, so the AUTO failsafe
# baseline is the quiet ~4,080 RPM (not the 14,800 jet-engine ramp). Self-contained:
# re-asserted every startup, so it survives reboots regardless of iDRAC persistence.
ipmitool raw 0x30 0xce 0x00 0x16 0x05 0x00 0x00 0x00 0x05 0x00 0x01 0x00 0x00 >/dev/null 2>&1 \
	&& log "third-party PCIe fan response -> Disabled (quiet auto baseline)"

fails=0
last=-1
log "gpu-fan-control started (poll=${POLL}s floor=${FLOOR}% exhaust_trip=${EXHAUST_TRIP}C)"

while :; do
	gt=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader,nounits 2>/dev/null | sort -rn | head -1)
	if ! [[ "$gt" =~ ^[0-9]+$ ]]; then
		fails=$((fails + 1))
		log "WARN nvidia-smi read failed (${fails}/${MAXFAILS}) -> AUTO"
		fan_auto
		[ "$fails" -ge "$MAXFAILS" ] && { log "giving up; leaving fans in AUTO"; exit 1; }
		sleep "$POLL"; continue
	fi
	fails=0

	# asymmetric hysteresis: ramp UP at temp, ramp DOWN only 2 C into the lower band
	up=$(curve "$gt"); down=$(curve "$((gt + 2))")
	if   [ "$up"   -gt "$last" ]; then target=$up
	elif [ "$down" -lt "$last" ]; then target=$down
	else target=$last; fi
	[ "$target" -lt "$FLOOR" ] && target=$FLOOR

	# chassis-wide safety net (catches CPU-driven heat the GPU curve can't see)
	ex=$(ipmitool sdr type temperature 2>/dev/null | awk -F'|' '/Exhaust Temp/{gsub(/[^0-9]/,"",$5); print $5}')
	if [[ "$ex" =~ ^[0-9]+$ ]] && [ "$ex" -ge "$EXHAUST_TRIP" ] && [ "$target" -lt 70 ]; then
		target=70
	fi

	if [ "$target" != "$last" ]; then
		fan_manual
		fan_set "$target"
		log "gpu=${gt}C exhaust=${ex:-?}C -> fan ${target}%"
		last=$target
	fi
	sleep "$POLL"
done
