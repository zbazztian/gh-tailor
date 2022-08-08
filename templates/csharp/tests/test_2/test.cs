using System;
using System.IO;
using System.Web;

public class TaintedPathHandler : IHttpHandler {
//    public void ProcessRequest(HttpContext ctx) {
//        String path = ctx.Request.QueryString["page"];
//        // BAD: Used via a File.Create... call.
//        using (StreamWriter sw = File.CreateText(path)) {
//            sw.WriteLine("Hello");
//        }
//    }
}
