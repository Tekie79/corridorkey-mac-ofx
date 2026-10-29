"""Scoped attention compatibility adapters; never patch the global Torch API.

The forward math below follows the pinned CorridorKey full-attention modules.
Only tensor contiguity at the SDPA boundary changes. Weights, normalization,
RoPE, head gating, precision, complete key/value context and output are retained.
This adapter is activated only after its real-model reference comparison passes.
"""
import types


def _full_attention(self,x,t_stride=1.0):
    import torch
    import torch.nn.functional as F
    from corridorkey.blocks import apply_rotary
    B,T,H,W,C=x.shape
    spatial=self._ckmac_spatial
    N=H*W if spatial else T*H*W
    batch=B*T if spatial else B
    chunk=int(getattr(self,'inference_query_chunk_tokens',0) or 0)
    if self.qkv_dw is not None:
        y=self.qkv_dw(self.qkv.qkv(x))
        qkv=y.reshape(batch,N,3,self.num_heads,self.head_dim).permute(2,0,3,1,4).contiguous()
        q,k,v=qkv.unbind(dim=0)
    else:
        q,k,v=self.qkv(x.reshape(batch,N,C))
    gate_tokens=x.reshape(batch,N,C)
    if self.qk_norm:q,k=self.q_norm(q),self.k_norm(k)
    if spatial:cos,sin=self.rope.get_cos_sin(H,W,device=x.device)
    else:cos,sin=self.rope.get_cos_sin(T,H,W,device=x.device,t_stride=t_stride)
    q,k=apply_rotary(q,cos,sin),apply_rotary(k,cos,sin)
    k,v=k.contiguous(),v.contiguous()
    if chunk>0 and not self.training and N>chunk:
        attn=q.new_empty((batch,self.num_heads,N,self.head_dim))
        for start in range(0,N,chunk):
            end=min(start+chunk,N)
            out=F.scaled_dot_product_attention(q[:,:,start:end].contiguous(),k,v,dropout_p=0.,is_causal=False)
            attn[:,:,start:end]=self.attn_gate(gate_tokens[:,start:end].contiguous(),out)
    else:
        attn=F.scaled_dot_product_attention(q.contiguous(),k,v,dropout_p=0.,is_causal=False)
        attn=self.attn_gate(gate_tokens,attn)
    attn=attn.transpose(1,2).reshape(batch,N,C)
    return self.proj(attn).reshape(B,T,H,W,C)


def install_contiguous_attention(model):
    changed=[]
    for name,module in model.named_modules():
        kind=module.__class__.__name__
        if kind in ('FullSpatialAttention2D','FullAttention3D'):
            module._ckmac_spatial=kind=='FullSpatialAttention2D'
            module.forward=types.MethodType(_full_attention,module)
            changed.append(name)
    return changed
