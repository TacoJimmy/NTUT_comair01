'''
@author: NTUT
'''

import time
import serial
import modbus_tk.defines as cst
from modbus_tk import modbus_rtu
import paho.mqtt.client as mqtt
import json  
import threading
import schedule


# coding:utf-8
import codecs

master = modbus_rtu.RtuMaster(serial.Serial(port='/dev/ttyS1', baudrate=19200, bytesize=8, parity='N', stopbits=1, xonxoff=0))
master.set_timeout(5.0)
master.set_verbose(True)


evm_velocity = 3
temp_set = 26
comf_set = 1
evm_temp = 25
evm_humi = 60
evm_comfort = 1

def on_connect(client, userdata, flags, rc):
    print("Connected with result code"+str(rc))
    client.subscribe('v1/devices/me/rpc/request/+',1)
    time.sleep(3)

def on_message(client, userdata, msg):
    global comf_set
    global temp_set
    global evm_comfort
    data_topic = msg.topic
    data_payload = json.loads(msg.payload.decode())
    print(data_payload)
    comf_set = data_payload['params']
    
    listtopic = data_topic.split("/") 

def AC_PowerOn():
    
    while True:
        master.execute(3, cst.WRITE_SINGLE_REGISTER, 0, output_value=1)
        time.sleep(0.5)
        AC_Power = master.execute(3, cst.READ_HOLDING_REGISTERS, 0, 1)
        print (AC_Power)
        if AC_Power[0]==1: 
            break

def AC_PowerOff():
    
    while True:
        master.execute(3, cst.WRITE_SINGLE_REGISTER, 0, output_value=0)
        time.sleep(0.5)
        AC_Power = master.execute(3, cst.READ_HOLDING_REGISTERS, 0, 1)
        print (AC_Power)
        if AC_Power[0]==0: 
            break

def Fan_speed_OnOff():
    master.execute(1, cst.WRITE_MULTIPLE_REGISTERS, 1103,output_value=(1, 1))
    time.sleep(1)



def Fan_init_speed():
    for i in range (1,5):
        master.execute(1, cst.WRITE_MULTIPLE_REGISTERS, 1103,output_value=(2, 1))
        time.sleep(1)
        
def Fan_speed(speed):
    Fan_init_speed()
    for i in range (1,speed):
        master.execute(1, cst.WRITE_MULTIPLE_REGISTERS, 1103,output_value=(3, 1))
        time.sleep(1)
        
        

def AC_SetTemp(Temp_Value):
    time.sleep(1)
    master.execute(3, cst.WRITE_SINGLE_REGISTER, 3, output_value=Temp_Value)
    time.sleep(0.5)
    
def get_temp():
    global evm_temp,evm_humi
    temp = master.execute(2, cst.READ_INPUT_REGISTERS, 1, 2) 
    time.sleep(0.5)
    evm_temp = round(temp[0]*0.1-3,1)
    evm_humi = round(temp[1]*0.1,1)
    
    return evm_temp,evm_humi

def get_ACRoomTemp():
    temp = master.execute(3, cst.READ_HOLDING_REGISTERS, 4, 1) 
    time.sleep(0.5)
    
    return temp[0]

def comfort_cal(temp,humi,volcity):
    Comfort_numb = (1.818*temp+18.18)*(0.88+0.002*humi)+(temp-32)/(45-temp)-3.2*volcity+18.2
    return Comfort_numb

def comfort_defin(temp,humi,velocity):
    com_i = 0
    numb_comfort = comfort_cal(temp,humi,velocity)
    #print(numb_comfort)
    if numb_comfort > 85 :
        com_note = "感覺炎熱 +4"
        com_i = 4
    elif 80 < numb_comfort <= 85 :
        com_note = "感覺很熱 +3"
        com_i = 3
    elif 76 < numb_comfort <= 80 :
        com_note = "感覺偏熱 +2"
        com_i = 2
    elif 71 < numb_comfort <= 76 :
        com_note = "感覺偏暖 +1"
        com_i = 1
    elif 59 < numb_comfort <= 71 :
        com_note = "舒適 0"
        com_i = 0        
    elif 51 < numb_comfort <= 59 :
        com_note = "感覺略偏冷 -1"
        com_i = -1     
    elif 39 < numb_comfort <= 51 :
        com_note = "感覺較冷 -2"
        com_i = -2     
    elif 26 < numb_comfort <= 39 :
        com_note = "感覺很冷 -3"
        com_i = -3 
    elif numb_comfort <= 26 :
        com_note = "感覺寒冷 -4"
        com_i = -4 
    return numb_comfort,com_i,com_note
    
def set_speed(temp,humi):
    global evm_velocity
    global comf_set
    sequences = [0, 1, 2, 3, 4, 5]
    for i in sequences:
        test = comfort_defin(temp,humi,i)
        if test[1] <= comf_set:
            velocity = i
            break
        else:
            velocity = 5
    if velocity != evm_velocity :
        Fan_speed(velocity)
    evm_velocity = velocity
    
    
        
    
    return (velocity)


def job():
    global comf_set
    global temp_set
    global evm_comfort

    RTcond = get_temp()
    evm_temp = RTcond[0]
    evm_humi = RTcond[1]
    num_comfort = comfort_defin(RTcond[0],RTcond[1],3)
    print (num_comfort)
    print (RTcond)
    Fan_SetSpeed = set_speed(RTcond[0],RTcond[1])
    #Fan_speed(3)
    
    if evm_velocity > 3:
        if temp_set > 20 :
            temp_set = temp_set - 1
            AC_SetTemp(temp_set)
            
    if evm_velocity < 2:
        if temp_set <= 27 :
            temp_set = temp_set + 1
            AC_SetTemp(temp_set)
    print (temp_set)
    
    meter_token = 'IZcJiw4YcQFvDyBno9pd'
    meter_pass = ''
    url = 'thingsboard.cloud'

    client01 = mqtt.Client()
    client01.on_connect = on_connect
    client01.on_message = on_message
    client01.username_pw_set(meter_token, meter_pass)
    client01.connect(url, 1883, 60)
    
    payload = {'Temperature' : evm_temp, 'Humidity':evm_humi, 'comfortair':evm_comfort, 'FanSpeed':Fan_SetSpeed, 'TempSet':temp_set}
    client01.publish("v1/devices/me/telemetry", json.dumps(payload))
    

    time.sleep(1)
    
    


def job_pre():
    try:
        schedule.every(5).seconds.do(job)
        while True:
            schedule.run_pending()  
            time.sleep(1)
    except:
        pass

if __name__ == '__main__':
    while True:
        try:
            AC_PowerOn()
            time.sleep(1)
            Fan_speed_OnOff()
            time.sleep(1)
    
            t = threading.Thread(target = job_pre)
            t.start()
    
    
            meter_token = 'IZcJiw4YcQFvDyBno9pd'
            meter_pass = ''
            url = 'thingsboard.cloud'

            client02 = mqtt.Client()
            client02.on_connect = on_connect
            client02.on_message = on_message
            client02.username_pw_set(meter_token, meter_pass)
            client02.connect(url, 1883, 60)
    
            client02.loop_forever()
        except:
            pass
    
    
    '''
    print(get_ACRoomTemp())
    AC_PowerOn()
    AC_23()
    
    
    
    volcity  = 2
    evm = get_temp()
    print(evm)
    print(comfort_cal(evm[0],evm[1],volcity))
    print(comfort_defin(evm[0],evm[1],volcity))
    
    Fan_speed_OnOff()
    Fan_init_speed()
    time.sleep(10)
    
    
    
    
    Fan_speed(3)
    meter_token = 'IZcJiw4YcQFvDyBno9pd'
    meter_pass = ''
    url = 'thingsboard.cloud'

    client01 = mqtt.Client()
    client01.on_connect = on_connect
    client01.on_message = on_message
    client01.username_pw_set(meter_token, meter_pass)
    client01.connect(url, 1883, 60)
    client01.loop_forever()

    client02 = mqtt.Client()
    client02.username_pw_set(meter_token,"xxxx")
    client02.connect(url, 1883, 60)
    
    while True:
        RTcond = get_temp()
        num_comfort = comfort_defin(RTcond[0],RTcond[1],3)
        print (num_comfort)
        print (RTcond)
        print (set_speed(RTcond[0],RTcond[1]))
        time.sleep(5)
    
        if evm_velocity > 3:
            temp_set = temp_set - 1
            if temp_set == 20:
                AC_20()
            elif temp_set == 21:
                AC_21()
            elif temp_set == 22:
                AC_22()
            elif temp_set == 23:
                AC_23()
            elif temp_set == 24:
                AC_24()
            elif temp_set == 25:
                AC_25()
            elif temp_set == 26:
                AC_26()
            elif temp_set == 27:
                AC_27()
            
        if evm_velocity < 2:
            temp_set = temp_set + 1
            if temp_set == 20:
                AC_20()
            elif temp_set == 21:
                AC_21()
            elif temp_set == 22:
                AC_22()
            elif temp_set == 23:
                AC_23()
            elif temp_set == 24:
                AC_24()
            elif temp_set == 25:
                AC_25()
            elif temp_set == 26:
                AC_26()
            elif temp_set == 27:
                AC_27()
        time.sleep(5)
    '''
