package com.rezox.render.agent;

import java.net.URL;
import java.net.InetAddress;
import java.net.UnknownHostException;

/** DNS-free source validation, shared by initial fetches and redirect hops.
 * Hostname resolution remains the HTTPS transport's responsibility; this is
 * deliberately not a DNS-rebinding sandbox or an origin allowlist.
 */
final class FileTransferSources {
    private FileTransferSources(){}
    static URL checked(String raw)throws Exception {
        URL result=new URL(raw);
        if(!result.getProtocol().equals("https")||result.getHost().isEmpty()||result.getUserInfo()!=null||raw.length()>8192)
            throw new IllegalArgumentException("TRANSFER_REQUIRES_HTTPS_FILE_REFERENCE");
        String host=result.getHost().toLowerCase(java.util.Locale.ROOT);
        // URL.getHost retains brackets for IPv6 and a DNS root dot for FQDNs.
        if(host.startsWith("[")&&host.endsWith("]"))host=host.substring(1,host.length()-1);
        while(host.endsWith("."))host=host.substring(0,host.length()-1);
        if(host.equals("localhost")||host.endsWith(".localhost"))throw localSource();
        InetAddress literal=null;
        if(host.indexOf(':')>=0){
            // Only a literal IPv6 grammar can reach getByName. Never resolve a
            // hostname during validation; offline transfers must queue safely.
            if(!host.matches("[0-9a-f:.]+"))throw localSource();
            try{literal=InetAddress.getByName(host);}
            catch(UnknownHostException error){throw localSource();}
        }else if(host.matches("[0-9.]+")||host.matches("(?:0x[0-9a-f]+|[0-9]+)(?:\\.(?:0x[0-9a-f]+|[0-9]+)){0,3}")){
            // Reject legacy decimal/short/octal/hex forms instead of letting
            // Java and Android's resolver disagree about which IP they name.
            String[] parts=host.split("\\.",-1);
            if(parts.length!=4)throw localSource();
            byte[] bytes=new byte[4];
            for(int i=0;i<4;i++){
                if(!parts[i].matches("0|[1-9][0-9]{0,2}"))throw localSource();
                int value=Integer.parseInt(parts[i]);
                if(value>255)throw localSource();
                bytes[i]=(byte)value;
            }
            literal=InetAddress.getByAddress(bytes);
        }
        if(literal!=null&&localAddress(literal))throw localSource();
        return result;
    }
    private static IllegalArgumentException localSource(){
        return new IllegalArgumentException("LOCAL_NETWORK_SOURCE_UNAVAILABLE");
    }
    private static boolean localAddress(InetAddress address){
        if(address.isAnyLocalAddress()||address.isLoopbackAddress()||address.isLinkLocalAddress()
                ||address.isSiteLocalAddress()||address.isMulticastAddress())return true;
        byte[] bytes=address.getAddress();
        if(bytes.length==4){
            int a=bytes[0]&255,b=bytes[1]&255;
            return a==0||a>=240||(a==100&&b>=64&&b<=127)||(a==198&&(b==18||b==19));
        }
        if((bytes[0]&0xfe)==0xfc)return true; // IPv6 unique-local fc00::/7.
        // Deprecated IPv4-compatible ::/96 literals can encode loopback or
        // private IPv4. IPv4-mapped ::ffff:x already decodes to four bytes.
        for(int i=0;i<12;i++)if(bytes[i]!=0)return false;
        return true;
    }
}
