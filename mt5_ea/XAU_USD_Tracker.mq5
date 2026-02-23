//+------------------------------------------------------------------+
//|                                             XAU_USD_Tracker.mq5  |
//|                          XAU/USD Trading Tracker - Expert Advisor |
//|                                                                  |
//| Sends real-time XAUUSD trade data to a remote web dashboard      |
//| via HTTP POST. Designed for use with the Python/FastAPI tracker.  |
//|                                                                  |
//| SETUP:                                                           |
//| 1. Copy this file to: MT5_Data/MQL5/Experts/                     |
//| 2. In MT5: Tools > Options > Expert Advisors                     |
//|    - Check "Allow WebRequest for listed URL"                     |
//|    - Add your server URL (e.g. http://192.168.1.100:8000)        |
//| 3. Attach EA to any XAUUSD chart                                 |
//| 4. Enable AutoTrading                                            |
//+------------------------------------------------------------------+
#property copyright "XAU/USD Tracker"
#property version   "2.00"
#property strict

//--- Input parameters
input string   ServerURL    = "http://localhost:8000";  // Dashboard server URL
input string   ApiKey       = "";                       // API key (optional, must match TRACKER_API_KEY)
input int      PushInterval = 2;                        // Push interval in seconds
input int      HistoryDays  = 30;                       // Days of deal history to send
input bool     SendDeals    = true;                     // Send deal history

//--- Constants
#define SYMBOL_NAME "XAUUSD"

//--- Global variables
datetime lastPushTime = 0;
int      pushCount    = 0;
int      errorCount   = 0;

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   // Verify the symbol exists
   if(!SymbolSelect(SYMBOL_NAME, true))
   {
      Print("[Tracker] WARNING: ", SYMBOL_NAME, " not found. Trying alternate names...");
      // Some brokers use different names
      string alternates[] = {"XAUUSD", "XAUUSDm", "XAUUSD.", "GOLD", "GOLDm"};
      bool found = false;
      for(int i = 0; i < ArraySize(alternates); i++)
      {
         if(SymbolSelect(alternates[i], true))
         {
            Print("[Tracker] Found symbol: ", alternates[i]);
            found = true;
            break;
         }
      }
      if(!found)
         Print("[Tracker] WARNING: Could not find gold symbol. Positions/orders may be empty.");
   }

   Print("[Tracker] Expert Advisor initialized");
   Print("[Tracker] Server: ", ServerURL);
   Print("[Tracker] Push interval: ", PushInterval, " seconds");
   Print("[Tracker] API Key: ", StringLen(ApiKey) > 0 ? "SET" : "NOT SET");

   // Send initial data immediately
   PushData();

   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   Print("[Tracker] EA removed. Total pushes: ", pushCount, ", Errors: ", errorCount);
}

//+------------------------------------------------------------------+
//| Expert tick function                                              |
//+------------------------------------------------------------------+
void OnTick()
{
   // Push data at the configured interval
   if(TimeCurrent() - lastPushTime >= PushInterval)
   {
      PushData();
      lastPushTime = TimeCurrent();
   }
}

//+------------------------------------------------------------------+
//| Timer function (backup for when no ticks arrive)                  |
//+------------------------------------------------------------------+
void OnTimer()
{
   if(TimeCurrent() - lastPushTime >= PushInterval)
   {
      PushData();
      lastPushTime = TimeCurrent();
   }
}

//+------------------------------------------------------------------+
//| Build and send the JSON payload                                   |
//+------------------------------------------------------------------+
void PushData()
{
   string json = BuildJSON();

   string url = ServerURL + "/api/push";
   string headers = "Content-Type: application/json\r\n";
   if(StringLen(ApiKey) > 0)
      headers += "X-API-Key: " + ApiKey + "\r\n";

   char   postData[];
   char   result[];
   string resultHeaders;

   StringToCharArray(json, postData, 0, StringLen(json), CP_UTF8);

   // Resize to exact length (remove null terminator)
   ArrayResize(postData, StringLen(json));

   int timeout = 5000; // 5 second timeout
   int res = WebRequest("POST", url, headers, timeout, postData, result, resultHeaders);

   if(res == 200)
   {
      pushCount++;
      if(pushCount % 100 == 0)
         Print("[Tracker] Push #", pushCount, " successful");
   }
   else if(res == -1)
   {
      errorCount++;
      int lastErr = GetLastError();
      if(errorCount <= 5 || errorCount % 50 == 0)
      {
         Print("[Tracker] WebRequest failed. Error: ", lastErr);
         Print("[Tracker] Make sure URL is allowed in Tools > Options > Expert Advisors");
         Print("[Tracker] URL: ", url);
      }
   }
   else
   {
      errorCount++;
      string response = CharArrayToString(result, 0, WHOLE_ARRAY, CP_UTF8);
      if(errorCount <= 5 || errorCount % 50 == 0)
         Print("[Tracker] HTTP ", res, ": ", response);
   }
}

//+------------------------------------------------------------------+
//| Build the full JSON payload                                       |
//+------------------------------------------------------------------+
string BuildJSON()
{
   string json = "{";

   // Account info
   json += "\"account\":" + BuildAccountJSON() + ",";

   // Price
   json += "\"price\":" + BuildPriceJSON() + ",";

   // Positions
   json += "\"positions\":" + BuildPositionsJSON() + ",";

   // Orders
   json += "\"orders\":" + BuildOrdersJSON();

   // Deals (history) - only send periodically to reduce bandwidth
   if(SendDeals && pushCount % 30 == 0)  // Every ~60 seconds at 2s interval
   {
      json += ",\"deals\":" + BuildDealsJSON();
   }

   json += "}";
   return json;
}

//+------------------------------------------------------------------+
//| Build account JSON                                                |
//+------------------------------------------------------------------+
string BuildAccountJSON()
{
   string json = "{";
   json += "\"login\":" + IntegerToString(AccountInfoInteger(ACCOUNT_LOGIN)) + ",";
   json += "\"balance\":" + DoubleToString(AccountInfoDouble(ACCOUNT_BALANCE), 2) + ",";
   json += "\"equity\":" + DoubleToString(AccountInfoDouble(ACCOUNT_EQUITY), 2) + ",";
   json += "\"margin\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN), 2) + ",";
   json += "\"free_margin\":" + DoubleToString(AccountInfoDouble(ACCOUNT_MARGIN_FREE), 2) + ",";

   double marginLevel = AccountInfoDouble(ACCOUNT_MARGIN_LEVEL);
   json += "\"margin_level\":" + DoubleToString(marginLevel, 2) + ",";

   json += "\"profit\":" + DoubleToString(AccountInfoDouble(ACCOUNT_PROFIT), 2) + ",";
   json += "\"currency\":\"" + AccountInfoString(ACCOUNT_CURRENCY) + "\",";
   json += "\"server\":\"" + AccountInfoString(ACCOUNT_SERVER) + "\",";
   json += "\"name\":\"" + EscapeJSON(AccountInfoString(ACCOUNT_NAME)) + "\"";
   json += "}";
   return json;
}

//+------------------------------------------------------------------+
//| Build price JSON                                                  |
//+------------------------------------------------------------------+
string BuildPriceJSON()
{
   MqlTick tick;
   string json = "{";

   if(SymbolInfoTick(SYMBOL_NAME, tick))
   {
      double spread = tick.ask - tick.bid;
      json += "\"symbol\":\"" + SYMBOL_NAME + "\",";
      json += "\"bid\":" + DoubleToString(tick.bid, 2) + ",";
      json += "\"ask\":" + DoubleToString(tick.ask, 2) + ",";
      json += "\"spread\":" + DoubleToString(spread, 2) + ",";
      json += "\"time\":\"" + TimeToString(tick.time, TIME_DATE | TIME_SECONDS) + "\"";
   }
   else
   {
      json += "\"symbol\":\"" + SYMBOL_NAME + "\",";
      json += "\"bid\":0,\"ask\":0,\"spread\":0,\"time\":\"\"";
   }

   json += "}";
   return json;
}

//+------------------------------------------------------------------+
//| Build positions JSON array                                        |
//+------------------------------------------------------------------+
string BuildPositionsJSON()
{
   string json = "[";
   int total = PositionsTotal();
   bool first = true;

   for(int i = 0; i < total; i++)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket == 0) continue;

      string symbol = PositionGetString(POSITION_SYMBOL);
      // Accept XAUUSD and common variants
      if(StringFind(symbol, "XAU") < 0 && StringFind(symbol, "GOLD") < 0)
         continue;

      if(!first) json += ",";
      first = false;

      string posType = PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "BUY" : "SELL";

      json += "{";
      json += "\"ticket\":" + IntegerToString((long)ticket) + ",";
      json += "\"symbol\":\"" + symbol + "\",";
      json += "\"type\":\"" + posType + "\",";
      json += "\"volume\":" + DoubleToString(PositionGetDouble(POSITION_VOLUME), 2) + ",";
      json += "\"open_price\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN), 2) + ",";
      json += "\"current_price\":" + DoubleToString(PositionGetDouble(POSITION_PRICE_CURRENT), 2) + ",";
      json += "\"sl\":" + DoubleToString(PositionGetDouble(POSITION_SL), 2) + ",";
      json += "\"tp\":" + DoubleToString(PositionGetDouble(POSITION_TP), 2) + ",";
      json += "\"profit\":" + DoubleToString(PositionGetDouble(POSITION_PROFIT), 2) + ",";
      json += "\"swap\":" + DoubleToString(PositionGetDouble(POSITION_SWAP), 2) + ",";
      json += "\"commission\":" + DoubleToString(PositionGetDouble(POSITION_COMMISSION), 2) + ",";
      json += "\"open_time\":\"" + TimeToString((datetime)PositionGetInteger(POSITION_TIME), TIME_DATE | TIME_SECONDS) + "\",";
      json += "\"magic\":" + IntegerToString(PositionGetInteger(POSITION_MAGIC)) + ",";
      json += "\"comment\":\"" + EscapeJSON(PositionGetString(POSITION_COMMENT)) + "\"";
      json += "}";
   }

   json += "]";
   return json;
}

//+------------------------------------------------------------------+
//| Build pending orders JSON array                                   |
//+------------------------------------------------------------------+
string BuildOrdersJSON()
{
   string json = "[";
   int total = OrdersTotal();
   bool first = true;

   for(int i = 0; i < total; i++)
   {
      ulong ticket = OrderGetTicket(i);
      if(ticket == 0) continue;

      string symbol = OrderGetString(ORDER_SYMBOL);
      if(StringFind(symbol, "XAU") < 0 && StringFind(symbol, "GOLD") < 0)
         continue;

      if(!first) json += ",";
      first = false;

      string orderType = OrderTypeToString((ENUM_ORDER_TYPE)OrderGetInteger(ORDER_TYPE));

      json += "{";
      json += "\"ticket\":" + IntegerToString((long)ticket) + ",";
      json += "\"symbol\":\"" + symbol + "\",";
      json += "\"type\":\"" + orderType + "\",";
      json += "\"volume\":" + DoubleToString(OrderGetDouble(ORDER_VOLUME_CURRENT), 2) + ",";
      json += "\"price\":" + DoubleToString(OrderGetDouble(ORDER_PRICE_OPEN), 2) + ",";
      json += "\"sl\":" + DoubleToString(OrderGetDouble(ORDER_SL), 2) + ",";
      json += "\"tp\":" + DoubleToString(OrderGetDouble(ORDER_TP), 2) + ",";
      json += "\"time_setup\":\"" + TimeToString((datetime)OrderGetInteger(ORDER_TIME_SETUP), TIME_DATE | TIME_SECONDS) + "\",";
      json += "\"magic\":" + IntegerToString(OrderGetInteger(ORDER_MAGIC)) + ",";
      json += "\"comment\":\"" + EscapeJSON(OrderGetString(ORDER_COMMENT)) + "\"";
      json += "}";
   }

   json += "]";
   return json;
}

//+------------------------------------------------------------------+
//| Build deals (trade history) JSON array                            |
//+------------------------------------------------------------------+
string BuildDealsJSON()
{
   string json = "[";

   datetime dateFrom = TimeCurrent() - HistoryDays * 86400;
   datetime dateTo   = TimeCurrent();

   if(!HistorySelect(dateFrom, dateTo))
   {
      json += "]";
      return json;
   }

   int total = HistoryDealsTotal();
   bool first = true;

   for(int i = 0; i < total; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;

      string symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
      if(StringFind(symbol, "XAU") < 0 && StringFind(symbol, "GOLD") < 0)
         continue;

      if(!first) json += ",";
      first = false;

      string dealType  = DealTypeToString((ENUM_DEAL_TYPE)HistoryDealGetInteger(ticket, DEAL_TYPE));
      string dealEntry = DealEntryToString((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY));

      json += "{";
      json += "\"ticket\":" + IntegerToString((long)ticket) + ",";
      json += "\"order\":" + IntegerToString((long)HistoryDealGetInteger(ticket, DEAL_ORDER)) + ",";
      json += "\"symbol\":\"" + symbol + "\",";
      json += "\"type\":\"" + dealType + "\",";
      json += "\"volume\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_VOLUME), 2) + ",";
      json += "\"price\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_PRICE), 2) + ",";
      json += "\"profit\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_PROFIT), 2) + ",";
      json += "\"swap\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_SWAP), 2) + ",";
      json += "\"commission\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_COMMISSION), 2) + ",";
      json += "\"fee\":" + DoubleToString(HistoryDealGetDouble(ticket, DEAL_FEE), 2) + ",";
      json += "\"time\":\"" + TimeToString((datetime)HistoryDealGetInteger(ticket, DEAL_TIME), TIME_DATE | TIME_SECONDS) + "\",";
      json += "\"magic\":" + IntegerToString(HistoryDealGetInteger(ticket, DEAL_MAGIC)) + ",";
      json += "\"comment\":\"" + EscapeJSON(HistoryDealGetString(ticket, DEAL_COMMENT)) + "\",";
      json += "\"entry\":\"" + dealEntry + "\"";
      json += "}";
   }

   json += "]";
   return json;
}

//+------------------------------------------------------------------+
//| Convert order type enum to string                                 |
//+------------------------------------------------------------------+
string OrderTypeToString(ENUM_ORDER_TYPE type)
{
   switch(type)
   {
      case ORDER_TYPE_BUY:             return "BUY";
      case ORDER_TYPE_SELL:            return "SELL";
      case ORDER_TYPE_BUY_LIMIT:       return "BUY_LIMIT";
      case ORDER_TYPE_SELL_LIMIT:      return "SELL_LIMIT";
      case ORDER_TYPE_BUY_STOP:        return "BUY_STOP";
      case ORDER_TYPE_SELL_STOP:       return "SELL_STOP";
      case ORDER_TYPE_BUY_STOP_LIMIT:  return "BUY_STOP_LIMIT";
      case ORDER_TYPE_SELL_STOP_LIMIT: return "SELL_STOP_LIMIT";
      default: return "UNKNOWN";
   }
}

//+------------------------------------------------------------------+
//| Convert deal type enum to string                                  |
//+------------------------------------------------------------------+
string DealTypeToString(ENUM_DEAL_TYPE type)
{
   switch(type)
   {
      case DEAL_TYPE_BUY:        return "BUY";
      case DEAL_TYPE_SELL:       return "SELL";
      case DEAL_TYPE_BALANCE:    return "BALANCE";
      case DEAL_TYPE_CREDIT:     return "CREDIT";
      case DEAL_TYPE_CHARGE:     return "CHARGE";
      case DEAL_TYPE_CORRECTION: return "CORRECTION";
      default: return "UNKNOWN";
   }
}

//+------------------------------------------------------------------+
//| Convert deal entry enum to string                                 |
//+------------------------------------------------------------------+
string DealEntryToString(ENUM_DEAL_ENTRY entry)
{
   switch(entry)
   {
      case DEAL_ENTRY_IN:     return "IN";
      case DEAL_ENTRY_OUT:    return "OUT";
      case DEAL_ENTRY_INOUT:  return "INOUT";
      case DEAL_ENTRY_OUT_BY: return "OUT_BY";
      default: return "UNKNOWN";
   }
}

//+------------------------------------------------------------------+
//| Escape special characters for JSON string values                  |
//+------------------------------------------------------------------+
string EscapeJSON(string text)
{
   StringReplace(text, "\\", "\\\\");
   StringReplace(text, "\"", "\\\"");
   StringReplace(text, "\n", "\\n");
   StringReplace(text, "\r", "\\r");
   StringReplace(text, "\t", "\\t");
   return text;
}
//+------------------------------------------------------------------+
