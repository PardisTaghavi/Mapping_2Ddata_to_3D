#!/usr/bin/env python3

'''
Author: Pardis Taghavi, Jonas Lossner
Texas A&M University - Fall 2022
'''

from pyexpat.errors import XML_ERROR_ENTITY_DECLARED_IN_PE
from re import L
from smtplib import LMTP
import sys
from tkinter import X
from xml.etree.ElementTree import XML
sys.path.insert(1, "/home/avalocal/catkin_ws/src/laneatt_ros")
sys.path.insert(1, "/home/avalocal/Desktop/rosSeg/src/mmsegmentation_ros")

import std_msgs.msg
import rospy
import numpy as np
from sensor_msgs.msg import PointCloud2, Image, CameraInfo
import message_filters
from laneatt_ros.msg import DetectedLane
from laneatt_ros.msg import DetectedRoadArea
import sensor_msgs.point_cloud2 as pc2
import ros_numpy
from scipy import interpolate
import numpy as np
from scipy.interpolate import RegularGridInterpolator
#########DATA

#tf transfer matrix between lidar-camera


#print(data['camera_matrix']['data'])
#################################################################################################

#D=np.array([D: [-0.245253, 0.149647, 0.003117, 0.000761, 0.0]]

#The following should be replaced by subscribing to the /camera_info topic as well as the /tf topics



P3_rect=np.array([[7.215377000000e+02, 0.000000000000e+00, 6.095593000000e+02, -3.395242000000e+02],
                  [0.000000000000e+00, 7.215377000000e+02, 1.728540000000e+02, 2.199936000000e+00],
                   [0.000000000000e+00, 0.000000000000e+00, 1.000000000000e+00, 2.729905000000e-03]])


R0_rect=np.array([[9.999239000000e-01, 9.837760000000e-03, -7.445048000000e-03, 0.00000],
                 [-9.869795000000e-03, 9.999421000000e-01, -4.278459000000e-03, 0.00000],
                  [7.402527000000e-03, 4.351614000000e-03, 9.999631000000e-01, 0.00000],
                  [0.000000,           0.000000,               0.000000,   1.00000]])




rect=np.array([[7.215377000000e+02, 0.000000000000e+00, 6.095593000000e+02, -3.395242000000e+02],
                  [0.000000000000e+00, 7.215377000000e+02, 1.728540000000e+02, 2.199936000000e+00],
                   [0.000000000000e+00, 0.000000000000e+00, 1.000000000000e+00, 2.729905000000e-03]])




#mtx=np.array([[3407.91772, 0.0000000000, 1066.72048],
 #               [0.00000000, 3451.94116, 825.36976],
  #              [0.0000000000, 0.0000000000, 1.0000000]])

#R0_rect=np.array([[9.999239000000e-01, 9.837760000000e-03, -7.445048000000e-03, 0.00000],
 #                [-9.869795000000e-03, 9.999421000000e-01, -4.278459000000e-03, 0.00000],
  #                [7.402527000000e-03, 4.351614000000e-03, 9.999631000000e-01, 0.00000],
  #                [0.000000,           0.000000,               0.000000,   1.00000]])



T1=np.array([[7.533745000000e-03, -9.999714000000e-01, -6.166020000000e-04, -4.069766000000e-03],
                    [1.480249000000e-02, 7.280733000000e-04, -9.998902000000e-01, -7.631618000000e-02],
                     [9.998621000000e-01, 7.523790000000e-03, 1.480755000000e-02, -2.717806000000e-01],
                     [0.000000,           0.000000,               0.000000,   1.00000]])




#D= np.array([-0.245253, 0.149647, 0.003117, 0.000761, 0.0])
##################################################################################################
def inverse_rigid_transformation(arr):
    irt=np.zeros_like(arr)
    Rt=np.transpose(arr[:3,:3])
    tt=-np.matmul(Rt,arr[:3,3])
    irt[:3,:3]=Rt
    irt[0,3]=tt[0]
    irt[1,3]=tt[1]
    irt[2,3]=tt[2]
    irt[3,3]=1
    return irt

#print(inverse_rigid_transformation(lidar_extrinsic))
##################################################################################################

#T_vel_cam=inverse_rigid_transformation(T1)
#print(T_vel_cam)
T_vel_cam=T1

##############################################################################################
lim_x=[3, 50]
lim_y=[-15,15]
lim_z=[-5,5]
height= 375
width= 1242

pixel_lim=2
##############################################################################################

class realCoor():
    
    def __init__(self):

        self.p_pub = rospy.Publisher("/used_pcl", PointCloud2, queue_size=1)
        self.seg_pub = rospy.Publisher("/segmented_pcl", PointCloud2, queue_size=1)

        self.fields = [pc2.PointField(name='x', offset=0, datatype=pc2.PointField.FLOAT32, count=1),pc2.PointField(name='y', offset=4,datatype=pc2.PointField.FLOAT32, count=1),pc2.PointField(name='z', offset=8,datatype=pc2.PointField.FLOAT32, count=1),pc2.PointField(name='intensity', offset=12,datatype=pc2.PointField.FLOAT32, count=1)]

        self.pcdSub=message_filters.Subscriber("/kitti/velo/pointcloud", PointCloud2)
        self.used_pointcloud = PointCloud2() #rospy.subscriber
        self.segSub=message_filters.Subscriber("/mmsegmentor/roadarea", DetectedRoadArea)
        self.header = std_msgs.msg.Header()
        self.header.frame_id = 'velo_link'
        pointcloud=[]
        
        #not working yet - probably need to re-write the way the road points are output from mmsegmentation similiar to the laneatt ones
        ds=message_filters.ApproximateTimeSynchronizer(([self.pcdSub, self.segSub]),1, 1.0)
        ds.registerCallback(self.segmentation_callback)

        self.vis=True
        print("realCoor initialized")
        rospy.spin()
        
    def create_cloud(self,line_3d, which):
    
        self.header.stamp = rospy.Time.now()
        
        if which == 0:
            self.lane_pointcloud = pc2.create_cloud(self.header, self.fields, line_3d)
            self.pcl_pub.publish(self.lane_pointcloud)
        elif which ==1:
            self.used_pointcloud = pc2.create_cloud(self.header, self.fields, line_3d)
            self.p_pub.publish(self.used_pointcloud)
        elif which ==2:
            self.used_pointcloud = pc2.create_cloud(self.header, self.fields, line_3d)
            self.seg_pub.publish(self.used_pointcloud)

    def segmentation_callback(self,msgLidar, msgPoint):
        
        start_time_seg = rospy.Time.now().to_sec()

        if msgPoint.RoadArea!=[]:
           
            #print("update mmseg")
            arr=np.array(msgPoint.RoadArea.data)
            msgPoint = np.array(msgPoint.RoadArea.data).reshape(width, height)
            msgPoint = np.flip(msgPoint, 0)
            road_pixels = np.where(msgPoint == 1.)
            road_pixels = (np.transpose(road_pixels)) # (x,y pixel coordinates of where the segmented road is within the image)
            pc = ros_numpy.numpify(msgLidar)
            points=np.zeros((pc.shape[0],4))
            points[:,0]=pc['x']
            points[:,1]=pc['y']
            points[:,2]=pc['z']
            points[:,3]=1

            pc_arr=self.crop_pointcloud(points) #to reduce computational expense
            pc_arr_pick=np.transpose(pc_arr)       

            m1=np.matmul(T_vel_cam,pc_arr_pick)#4*N
            m2=np.matmul(R0_rect,m1)
            uv1= np.matmul(P3_rect,m2) #4*N        

            uv1[0,:]=  np.divide(uv1[0,:],uv1[2,:])
            uv1[1,:]=  np.divide(uv1[1,:],uv1[2,:])

            line_3d=[]
            u=uv1[0,:]
            v=uv1[1,:]

            intersections1 = self.isin_tolerance(u, road_pixels[:,0],pixel_lim)
            intersections2 = self.isin_tolerance(v, road_pixels[:,1],pixel_lim)
            #isin_tolerance pulled from here: https://stackoverflow.com/questions/51744613/numpy-setdiff1d-with-tolerance-comparing-a-numpy-array-to-another-and-saving-o/51747164#51747164

            idx = (np.where(np.logical_and(intersections1 == True , intersections2 == True)))
            idx = np.array(idx)

            if idx.shape[1] > 0:

                line_3d=np.vstack((pc_arr_pick[0][idx[:]],pc_arr_pick[1][idx[:]],pc_arr_pick[2][idx[:]],np.ones((1,idx.shape[1]))))#, np.ones(idx.shape)]]
            else:
                rospy.logerr('no matching points between image pixel and lidar points!')

            if self.vis == True and line_3d!=[]:
                line_3d=np.array(np.transpose(line_3d))          
                _, idx=np.unique(line_3d[:,0:2], axis=0, return_index=True)
                line_3d_unique=line_3d[idx]
                self.create_cloud(line_3d_unique,2)
                #self.create_cloud(pc_arr,1) #uncomment this line to publish the cropped
            else:
                rospy.logwarn("Visualization is disabled - no pointcloud published")

            time_end_seg = rospy.Time.now().to_sec()
                            
            print("Segmentation time :: ", (start_time_seg - time_end_seg))


    def isin_tolerance(self,A, B, tol):
        A = np.asarray(A)
        B = np.asarray(B)

        Bs = np.sort(B) # skip if already sorted
        idx = np.searchsorted(Bs, A)

        linvalid_mask = idx==len(B)
        idx[linvalid_mask] = len(B)-1
        lval = Bs[idx] - A
        lval[linvalid_mask] *=-1

        rinvalid_mask = idx==0
        idx1 = idx-1
        idx1[rinvalid_mask] = 0
        rval = A - Bs[idx1]
        rval[rinvalid_mask] *=-1
        return np.minimum(lval, rval) <= tol
     
    def crop_pointcloud(self, pointcloud):
        # remove points outside of detection cube defined in 'configs.lim_*'
        mask = np.where((pointcloud[:, 0] >= lim_x[0]) & (pointcloud[:, 0] <= lim_x[1]) & (pointcloud[:, 1] >=lim_y[0]) & (pointcloud[:, 1] <= lim_y[1]) & (pointcloud[:, 2] >= lim_z[0]) & (pointcloud[:, 2] <= lim_z[1]))
        pointcloud = pointcloud[mask]
        return pointcloud
        
    def test(self, line):
        output = []
        line = np.array(line)
        indd=np.lexsort((line[:,2],line[:,1],line[:,0]))
        line=line[indd]
        _, idx=np.unique(line[:,0:2], axis=0, return_index=True)
        line =line[idx]
        #print("line::", line)
        x = -np.sort(-line[:,0])
        y =  -np.sort(-line[:,1])
        z =  -np.sort(-line[:,2])
        # print("xyz", x,y,z)
        intensity = line[:,3]
        npts = len(x)
        s = np.zeros(npts, dtype=float)
        
        xl=np.linspace(np.amax(x), np.amin(x), 500)
        yl=np.linspace(np.amax(y), np.amin(y), 500)
        zl=np.linspace(np.amax(z), np.amin(z),500)

        # Create new interpolation function for each axis against the norm 
        data = np.concatenate((x[:, np.newaxis], y[:, np.newaxis],  z[:, np.newaxis]),  axis=1)

        # Calculate the mean of the points, i.e. the 'center' of the cloud
        datamean = data.mean(axis=0)

        #  SVD on the mean-centered data.
        uu, dd, vv = np.linalg.svd(data - datamean)

        # Now vv[0] contains the first principal component, i.e. the direction
        # vector of the 'best fit' line in the least squares sense.

        # Now generate some points along this best fit line, for plotting.

        # I use -7, 7 since the spread of the data is roughly 14
        # and we want it to have mean 0 (like the points we did
        # the svd on). Also, it's a straight line, so we only need 2 points.
        linepts = vv[0] * np.mgrid[-20:20:2j][:, np.newaxis]

        # shift by the mean to get the line in the right place
        linepts += datamean

        l=linepts[0,0]-linepts[1,0]
        m=linepts[0,1]-linepts[1,1]
        n=linepts[0,2]-linepts[1,2]

        t= (xl-linepts[0,0])/l
        xs=xl
        ys=(t)*m+linepts[0,1]
        zs=(t)*n+linepts[0,2]
        #print(xs,'---xs')
        
        return np.transpose([xs, ys, zs,np.ones(len(xs)) * 1.1])
##################################################################################################
if __name__=='__main__':
    rospy.init_node("segmentationTO3d")
    realCoor()















  