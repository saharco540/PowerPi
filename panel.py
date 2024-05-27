print ("Panel started")
#panel serve panel.py --allow-websocket-origin=*

import panel as pn
import param

pn.extension(loading_spinner='dots', loading_color='#00aa41', sizing_mode="stretch_width")
pn.param.ParamMethod.loading_indicator = True

import pandas as pd
import hvplot.pandas
import holoviews as hv
from holoviews import dim, opts

import pigpio
pi = pigpio.pi()

# import sensor module
import sensor

# Hover tool for voltage plot
from bokeh.models import HoverTool
voltage_hover = HoverTool(tooltips=[("ts", "@ts{0,0}"),("voltage", "@voltage"),("ms", "@ms{0,0}")]) 
# ina.configure(gain=ina.GAIN_AUTO,shunt_adc=ina.ADC_12BIT)

print("Done imports")

# Each of the following functions will be called when the corresponding tab is selected

def data_logger(active_tab,target_tab):
    if active_tab==target_tab: # To only run the function when the tab is active, recieved using param
        
        # Tab Widgets
        duration_wig = pn.widgets.IntInput(name='Duration [s]', value=2)
        interval_ms_wig = pn.widgets.FloatInput(name='Sample rate[ms]', value=0.3, min=0)
        data_lst_wig = pn.widgets.MultiChoice(name='Data', value=['current','voltage'], options=['current','voltage'])
        set_voltage_wig = pn.widgets.FloatInput(name='Set Constant Voltage [V]', value=0)
        set_gain_wig = pn.widgets.Select(name='Set Gain Multiplier (High is less sensetive) [V]', options=[-1,0,1,2,3], value=-1)
        '''
        Based on pi-ina219,
        GAIN_1_40MV = 0  # Maximum shunt voltage 40mV
        GAIN_2_80MV = 1  # Maximum shunt voltage 80mV
        GAIN_4_160MV = 2  # Maximum shunt voltage 160mV
        GAIN_8_320MV = 3  # Maximum shunt voltage 320mV
        GAIN_AUTO = -1  # Determine gain automatically
        '''
        save_to_file_wig = pn.widgets.TextInput(name='Saves to file -', value='/home/pi/csvs/sensor_data.csv') 
        save_to_file_on_the_fly_wig = pn.widgets.Checkbox(name='Save to file on the fly', value=True)
        time_view_wig = pn.widgets.Select(name='X-Axis view',options=['Real time','Sample time'],value='Sample time')

        # Class for listening to button click
        class DataLoggingAction(param.Parameterized):
            # create a button that when pushed triggers method 'button'
            button = param.Action(lambda x: x.param.trigger('button'), label='Start measurments')

            process_done = None

            # method keeps on watching whether button is triggered
            @param.depends('button', watch=True)
            def get_readings(self):
                self.sensor_df = sensor.get_data_logger(data_lst=data_lst_wig.value,max_time_s=duration_wig.value,interval_ms=interval_ms_wig.value,set_voltage=set_voltage_wig.value,save_to_file=save_to_file_wig.value,save_to_file_on_the_fly=save_to_file_on_the_fly_wig.value, set_gain=set_gain_wig.value)
                self.process_done = True

            # method is watching whether process_done is updated (meaning data is ready to be plotted)
            @param.depends('process_done', watch=True)
            def update_graph(self):
                if self.process_done:
                    self.sensor_df['ts_diff_ms']=self.sensor_df['ts'].diff()*1000
                    if "voltage" not in data_lst_wig.value:
                        print(data_lst_wig.value)
                        self.sensor_df['voltage']=set_voltage_wig.value
                    if "current" not in data_lst_wig.value:
                        self.sensor_df['current']=0
                    self.sensor_df['wattage']=self.sensor_df['current']*self.sensor_df['voltage']
                    self.sensor_df['mW/h']=self.sensor_df['wattage']*(self.sensor_df['ts_diff_ms']/1000/3600)
                    self.sensor_df['mW/h_cumsum']=self.sensor_df['mW/h'].cumsum()
                    if time_view_wig.value=='Real time':
                        self.sensor_df['time']=pd.to_datetime(self.sensor_df['ts'],unit='s')
                        
                        x_axis='time'
                    elif time_view_wig.value == 'Sample time':
                        self.sensor_df['ms']=(self.sensor_df['ts']-self.sensor_df['ts'].iloc[0])*1000
                        x_axis='ms'
                    p = pn.Column() # plot Column
                    p.append(
                        pn.Column(
                            self.sensor_df.hvplot.line(x_axis,'current', title='Current [mA]'),
                            self.sensor_df.hvplot.line(x_axis,'voltage' ,title='Voltage [V]'),#.opts(tools=[voltage_hover]),
                            self.sensor_df.hvplot.line(x_axis,'wattage' ,title='Wattage [mW]'),
                            self.sensor_df.hvplot.line(x_axis,'mW/h_cumsum', title='Power consumption [mW/h]'),
                            f"{self.sensor_df['mW/h_cumsum'].max()}mW/h in {self.sensor_df['ts'].max()}ts = {self.sensor_df['mW/h_cumsum'].max()/(self.sensor_df['ts'].max()/1000)}mW/h each second",
                        )
                    )
                    return p
                                    
                else:
                    return "No data - Measure something..."
                
        dataLoggingLogic = DataLoggingAction()
        
        return pn.Column(
                pn.Column(
                    pn.Row(duration_wig,interval_ms_wig),
                    pn.Row(data_lst_wig,set_voltage_wig),
                    set_gain_wig
                ),
                save_to_file_on_the_fly_wig,
                save_to_file_wig,
                time_view_wig,
                dataLoggingLogic.param,
                dataLoggingLogic.update_graph
            )
    else:
        return "Tab is loading"
    
def live_view(active_tab,target_tab): 
    if active_tab==target_tab:
        ina = sensor.init_sensor(gain=-1)
        start=pi.get_current_tick()
        def get_plots(data):
            return (hv.Curve(data,'index','current').opts(width=1000, height=300)+hv.Curve(data,'index','voltage').opts(width=1000, height=300)).cols(1)


        # Set up StreamingDataFrame and add async callback
        mem_stream = hv.streams.Buffer(sensor.get_sensor_data(ina,start,['current','voltage']))

        # Define DynamicMaps and display plot
        mem_dmap = hv.DynamicMap(get_plots, streams=[mem_stream])
        plot = mem_dmap
        # Create PeriodicCallback which run every 500 milliseconds
        def cb():
            df_ = sensor.get_sensor_data(ina,start,['current','voltage'])
            mem_stream.send(df_)

        callback = pn.io.PeriodicCallback(callback=cb, period=1)
        callback.start()
        return (plot)
    else:
        return "Tab is loading"

# Load a csv file located locally by path from string widget to pandas dataframe and scatter plot it
def data_explorer(active_tab,target_tab):
    if active_tab==target_tab:
        
        # Load a csv file located locally by path from string widget to pandas dataframe and scatter plot it
        path_wig = pn.widgets.TextInput(name='Path', value='/home/pi/csvs/sensor_data.csv')
        time_view_wig = pn.widgets.Select(name='X-Axis view',options=['Real time','Sample time'],value='Sample time')
        @pn.depends(path_wig.param.value, time_view_wig.param.value)
        def load_csv(path, time_view):
            try:
                df = pd.read_csv(path)
                # wig_x_axis=pn.widgets.Select(name='X axis', options=list(df.columns), value=list(df.columns)[0])
                # wig_y_axis=pn.widgets.Select(name='Y axis', options=list(df.columns), value=list(df.columns)[1])
                # wig_plot_type=pn.widgets.Select(name='Plot type', options=['Scatter','Line','Step'], value='Step')
                # @pn.depends(wig_x_axis.param.value,wig_y_axis.param.value, wig_plot_type.param.value)
                # def plot_data(x_axis,y_axis,plot_type):
                    # if plot_type=='Scatter':
                    #     return (df.hvplot.scatter(x_axis,y_axis))
                    # elif plot_type=='Line':
                    #     return (df.hvplot.line(x_axis,y_axis))
                    # elif plot_type=='Step':
                    #     return (df.hvplot.step(x_axis,y_axis))
                                        
                # return pn.Column(wig_x_axis,wig_y_axis,wig_plot_type,plot_data)
                df['ts_diff_ms']=df['ts'].diff()*1000
                df['wattage']=df['current']*df['voltage']
                df['mW/h']=df['wattage']*(df['ts_diff_ms']/1000/3600)
                df['mW/h_cumsum']=df['mW/h'].cumsum()
                df['time']=pd.to_datetime(df['ts'],unit='s')
                df['ms']=(df['ts']-df['ts'].iloc[0])*1000
                if time_view=='Real time':
                    x_axis='time'
                elif time_view == 'Sample time':
                    x_axis='ms'
                p = pn.Column()
                p.append(
                    pn.Column(
                        df.hvplot.line(x_axis,'current', title='Current [mA]'),
                        df.hvplot.line(x_axis,'voltage' ,title='Voltage [V]'),#.opts(tools=[voltage_hover]),
                        df.hvplot.line(x_axis,'wattage' ,title='Wattage [mW]'),
                        df.hvplot.line(x_axis,'mW/h_cumsum', title='Power consumption [mW/h]'),
                        f"{df['mW/h_cumsum'].max():.5f} mW/h in {df['ms'].max()/1000:.5f} seconds = {df['mW/h_cumsum'].max()/(df['ts'].max()/1000):.5f} mW/h each second",
                    )
                )
                # if time_view == 'Sample time':
                #     p.append(
                #         pn.Column(
                #             (df["ts_diff_ms"]).describe()
                #         )
                #     )
                return p
            except Exception as e:
                return str(e)
        return pn.Column(
            time_view_wig,
            path_wig,
            load_csv
        )


from functools import partial
tabs = pn.Tabs(sizing_mode="stretch_width")
p1 = ('Data Logger', pn.depends(tabs.param.active)(partial(data_logger, target_tab=0)))
tabs.append(p1)
p2 = ('Live View', pn.depends(tabs.param.active)(partial(live_view, target_tab=1)))
tabs.append(p2)
p3 = ('Data Explorer', pn.depends(tabs.param.active)(partial(data_explorer, target_tab=2)))
tabs.append(p3)
tabs.servable(title = "PowerPi")
