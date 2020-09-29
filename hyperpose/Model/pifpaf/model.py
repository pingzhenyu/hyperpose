import tensorflow as tf
import tensorlayer as tl
from tensorlayer import layers
from tensorlayer.models import Model
from tensorlayer.layers import BatchNorm2d, Conv2d, DepthwiseConv2d, LayerList, MaxPool2d
from ..backbones import Resnet50_backbone

class Pifpaf(Model):
    def __init__(self,parts,limbs,n_pos=18,n_limbs=19,hin=368,win=368,backbone=None,pretraining=False,quad_size=2,data_format="channels_first"):
        super().__init__()
        self.parts=parts
        self.limbs=limbs
        self.n_pos=n_pos
        self.n_limbs=n_limbs
        self.quad_size=quad_size
        self.data_format=data_format
        #loss weights

        if(backbone==None):
            self.backbone=Resnet50_backbone(data_format=data_format,use_pool=False)
        else:
            self.backbone=backbone(data_format=data_format)
        self.pif_head=self.PifHead(input_features=self.backbone.out_channels,n_pos=self.n_pos,n_limbs=self.n_limbs,\
            quad_size=self.quad_size,data_format=self.data_format)
        self.paf_head=self.PafHead(input_features=self.backbone.out_channels,n_pos=self.n_pos,n_limbs=self.n_limbs,\
            quad_size=self.quad_size,data_format=self.data_format)
    
    @tf.function
    def forward(self,x):
        x=self.backbone.forward(x)
        pif_maps=self.pif_head.forward(x)
        paf_maps=self.paf_head.forward(x)
        return pif_maps,paf_maps
    
    @tf.function
    def infer(self,x):
        pif_maps,paf_maps=self.forward(x)
        pif_maps=tf.stack(pif_maps,axis=2)
        paf_maps=tf.stack(paf_maps,axis=2)
        return pif_maps,paf_maps
    
    def cal_loss(self,pd_pif_maps,pd_paf_maps,gt_pif_maps,gt_paf_maps):
        #calculate pif losses
        pd_pif_conf,pd_pif_vec,pd_pif_logb,pd_pif_scale=pd_pif_maps
        gt_pif_conf,gt_pif_vec,gt_pif_scale=gt_pif_maps
        loss_pif_conf=self.Bce_loss(pd_pif_conf,gt_pif_conf)
        loss_pif_vec=self.Laplace_loss(pd_pif_vec,pd_pif_logb,gt_pif_vec)
        loss_pif_scale=self.Scale_loss(pd_pif_scale,gt_pif_scale)
        loss_pif_maps=[loss_pif_conf,loss_pif_vec,loss_pif_scale]
        #calculate paf losses
        pd_paf_conf,pd_paf_src_vec,pd_paf_dst_vec,pd_paf_src_logb,pd_paf_dst_logb,pd_paf_src_scale,pd_paf_dst_scale=pd_paf_maps
        gt_paf_conf,gt_paf_src_vec,gt_paf_dst_vec,gt_paf_src_scale,gt_paf_dst_scale=gt_paf_maps
        loss_paf_conf=self.Bce_loss(pd_paf_conf,gt_paf_conf)
        loss_paf_src_vec=self.Laplace_loss(pd_paf_src_vec,pd_paf_src_logb,gt_paf_src_vec)
        loss_paf_dst_vec=self.Laplace_loss(pd_paf_dst_vec,pd_paf_dst_logb,gt_paf_dst_vec)
        loss_paf_src_scale=self.Scale_loss(pd_paf_src_scale,gt_paf_src_scale)
        loss_paf_dst_scale=self.Scale_loss(pd_paf_dst_scale,gt_paf_dst_scale)
        loss_paf_maps=[loss_paf_conf,loss_paf_src_vec,loss_paf_dst_vec,loss_paf_src_scale,loss_paf_dst_scale]
        #retun losses
        return loss_pif_maps,loss_paf_maps
    
    def Bce_loss(self,pd_conf,gt_conf)
        return loss_conf
    
    def Laplace_loss(self,pd_vec,pd_logb,gt_vec)
        return loss_vec
    
    def Scale_loss(self,pd_scale,gt_scale):
        return loss_scale
    
    class PifHead(Model):
        def __init__(self,input_features=2048,n_pos=19,n_limbs=19,quad_size=2,data_format="channels_first"):
            self.input_features=input_features
            self.n_pos=n_pos
            self.n_limbs=n_limbs
            self.quad_size=quad_size
            self.out_features=self.n_pos*5*(2**self.quad_size)
            self.data_format=data_format
            self.tf_data_format="NCHW" if self.data_format=="channels_first" else "NHWC"
            self.main_block=Conv2d(n_filter=self.out_features,in_channels=self.input_features,filter_size=(1,1),data_format=self.data_format)

        def forward(self,x):
            x=self.main_block.forward(x)
            x=tf.nn.depth_to_space(x,block_size=self.quad_size,data_format=self.tf_data_format)
            x=tf.reshape(x,[x.shape[0],self.n_pos,5,x.shape[2],x.shape[3]])
            pif_conf=x[:,:,0:1,:,:]
            pif_vec=x[:,:,1:3,:,:]
            pif_logb=x[:,:,3:4,:,:]
            pif_scale=x[:,:,4:5,:,:]
            #difference in paper and code
            #paper use sigmoid for conf_map in training while code not
            pif_conf=tf.nn.sigmoid(pif_conf)
            return pif_conf,pif_vec,pif_logb,pif_scale
        
    class PafHead(Model):
        def __init__(self,input_features=2048,n_pos=19,n_limbs=19,quad_size=2,data_format="channels_first"):
            self.input_features=input_features
            self.n_pos=n_pos
            self.n_limbs=n_limbs
            self.quad_size=quad_size
            self.out_features=self.n_limbs*9*(2**self.quad_size)
            self.data_format=data_format
            self.tf_data_format="NCHW" if self.data_format=="channels_first" else "NHWC"
            self.main_block=Conv2d(n_filter=self.out_features,in_channels=self.input_features,filter_size=(1,1),data_format=self.data_format)
        
        def forward(self,x):
            x=self.main_block.forward(x)
            x=tf.nn.depth_to_space(x,block_size=self.quad_size,data_format=self.tf_data_format)
            x=tf.reshape(x,[x.shape[0],self.n_limbs,9,x.shape[2],x.shape[3]])
            paf_conf=x[:,:,0:1,:,:]
            paf_src_vec=x[:,:,1:3,:,:]
            paf_dst_vec=x[:,:,3:5,:,:]
            paf_src_logb=x[:,:,5:6,:,:]
            paf_dst_logb=x[:,:,6:7,:,:]
            paf_src_scale=x[:,:,7:8,:,:]
            paf_dst_scale=x[:,:,8:9,:,:]
            #difference in paper and code
            #paper use sigmoid for conf_map in training while code not
            paf_conf=tf.nn.sigmoid(paf_conf)
            return paf_conf,paf_src_vec,paf_dst_vec,paf_src_logb,paf_dst_logb,paf_src_scale,paf_dst_scale
