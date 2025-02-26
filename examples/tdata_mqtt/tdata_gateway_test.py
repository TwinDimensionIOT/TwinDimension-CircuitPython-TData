# SPDX-FileCopyrightText: 2023 Luis Pichio, for TwinDimension
# SPDX-License-Identifier: MIT
import time
from random import randint

import ssl
import socketpool
import wifi
import adafruit_minimqtt.adafruit_minimqtt as MQTT
from tdata.tdata import TData_MQTT_Gateway
import json
import microcontroller
import gc

### WiFi ###

# Add a secrets.py to your filesystem that has a dictionary called secrets with "ssid" and
# "password" keys with your WiFi credentials. DO NOT share that file or commit it into Git or other
# source control.
# pylint: disable=no-name-in-module,wrong-import-order
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

print("Connecting to %s" % secrets["ssid"])
wifi.radio.connect(secrets["ssid"], secrets["password"])
print("Connected to %s!" % secrets["ssid"])


# Define callback functions which will be called when certain events happen.
# pylint: disable=unused-argument
def connected(client):
    # Connected function will be called when the client is connected to TDATA.
    print("Connected to T>DATA!")


def subscribe(client, userdata, topic, granted_qos):
    # This method is called when the client subscribes to a new topic.
    print("Subscribed to {0} with QOS level {1}".format(topic, granted_qos))


def unsubscribe(client, userdata, topic, pid):
    # This method is called when the client unsubscribes from a topic.
    print("Unsubscribed from {0} with PID {1}".format(topic, pid))

# pylint: disable=unused-argument


def disconnected(client):
    # Disconnected function will be called when the client disconnects.
    print("Disconnected from TDATA!")

# pylint: disable=unused-argument
def message(client, topic, payload):
    # Message function will be called when a subscribed topic has a new value.
    print("Message received from {0} with value: {1}".format(topic, payload))

def rpc(client, device_name, rpc_id, method, params):
    # Message function will be called when a RPC received for a device.
    print("RPC received for device {0} | rpc_id {1} | method {2} | params {3}".format(device_name, rpc_id, method, params))
    client.rpc_response(device_name, rpc_id, { "success": True })
    
# Create a socket pool
pool = socketpool.SocketPool(wifi.radio)

# Initialize a new MQTT Client object
mqtt_client = MQTT.MQTT(
    broker="tdata.tesacom.net",
    port=1883,
    username=secrets["tdata_gateway_token"],
    password="",
    socket_pool=pool,
    #    ssl_context=ssl.create_default_context(),
)

# Initialize an TData Client
tdata_gateway = TData_MQTT_Gateway(mqtt_client)

# Connect the callback methods defined above to TDATA
tdata_gateway.on_connect = connected
tdata_gateway.on_disconnect = disconnected
tdata_gateway.on_subscribe = subscribe
tdata_gateway.on_unsubscribe = unsubscribe
tdata_gateway.on_message = message
tdata_gateway.on_rpc = rpc

# Connect to TDATA
print("Connecting to TDATA...")
tdata_gateway.connect()

device_name = "EP(%02X:%02X:%02X:%02X:%02X:%02X)" % tuple(wifi.radio.mac_address)

print("Device connect")
tdata_gateway.device_connect(device_name)

print("Subscribe to rpc's")
tdata_gateway.subscribe_to_rpcs()

lastTelemetry = 0
lastAttributes = 0
print("Publishing telemetry every 10 seconds and attributes every 60...")
while True:
    # Explicitly pump the message loop.
    tdata_gateway.loop()
    # Send a new message every 10 seconds.
    if (time.monotonic() - lastTelemetry) >= 10:
        telemetry = {
            device_name: [
                {
                    "cpu.temperature": microcontroller.cpu.temperature,
                    "cpu.voltage": microcontroller.cpu.voltage,
                    "gc.mem_alloc": gc.mem_alloc(),
                    "gc.mem_free": gc.mem_free(),
                    "wifi.radio.ap_info.rssi": wifi.radio.ap_info.rssi,
                }
            ]
        }
        print("Publishing telemetry: ", telemetry)
        tdata_gateway.publish("telemetry", telemetry)
        lastTelemetry = time.monotonic()

    if (time.monotonic() - lastAttributes) >= 60:
        attributes = {
            device_name: {
                "radio.ipv4_address": wifi.radio.ipv4_address,
                "cpu.reset_reason": microcontroller.cpu.reset_reason,
                "cpu.frequency": microcontroller.cpu.frequency,
                "wifi.radio.ap_info.channel": wifi.radio.ap_info.channel,
                "wifi.radio.ap_info.ssid": wifi.radio.ap_info.ssid,
            }
        }
        print("Publishing attributes: ", attributes)
        tdata_gateway.publish("attributes", attributes)
        lastAttributes = time.monotonic()

