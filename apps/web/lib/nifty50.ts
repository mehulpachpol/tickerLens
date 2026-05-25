export type NiftyCompany = {
  ticker: string;
  name: string;
};

// Static seed list for UI convenience.
// Keep this list easy to replace with a backend-driven universe endpoint later.
export const NIFTY_50: NiftyCompany[] = [
  { ticker: "ADANIENT", name: "Adani Enterprises" },
  { ticker: "ADANIPORTS", name: "Adani Ports and SEZ" },
  { ticker: "APOLLOHOSP", name: "Apollo Hospitals" },
  { ticker: "ASIANPAINT", name: "Asian Paints" },
  { ticker: "AXISBANK", name: "Axis Bank" },
  { ticker: "BAJAJ-AUTO", name: "Bajaj Auto" },
  { ticker: "BAJFINANCE", name: "Bajaj Finance" },
  { ticker: "BAJAJFINSV", name: "Bajaj Finserv" },
  { ticker: "BEL", name: "Bharat Electronics" },
  { ticker: "BHARTIARTL", name: "Bharti Airtel" },
  { ticker: "BPCL", name: "BPCL" },
  { ticker: "BRITANNIA", name: "Britannia" },
  { ticker: "CIPLA", name: "Cipla" },
  { ticker: "COALINDIA", name: "Coal India" },
  { ticker: "DRREDDY", name: "Dr. Reddy’s Laboratories" },
  { ticker: "EICHERMOT", name: "Eicher Motors" },
  { ticker: "GRASIM", name: "Grasim" },
  { ticker: "HCLTECH", name: "HCL Technologies" },
  { ticker: "HDFCBANK", name: "HDFC Bank" },
  { ticker: "HDFCLIFE", name: "HDFC Life" },
  { ticker: "HEROMOTOCO", name: "Hero MotoCorp" },
  { ticker: "HINDALCO", name: "Hindalco" },
  { ticker: "HINDUNILVR", name: "Hindustan Unilever" },
  { ticker: "ICICIBANK", name: "ICICI Bank" },
  { ticker: "INDUSINDBK", name: "IndusInd Bank" },
  { ticker: "INFY", name: "Infosys" },
  { ticker: "ITC", name: "ITC" },
  { ticker: "JSWSTEEL", name: "JSW Steel" },
  { ticker: "KOTAKBANK", name: "Kotak Mahindra Bank" },
  { ticker: "LT", name: "Larsen & Toubro" },
  { ticker: "M&M", name: "Mahindra & Mahindra" },
  { ticker: "MARUTI", name: "Maruti Suzuki" },
  { ticker: "NESTLEIND", name: "Nestlé India" },
  { ticker: "NTPC", name: "NTPC" },
  { ticker: "ONGC", name: "ONGC" },
  { ticker: "POWERGRID", name: "Power Grid" },
  { ticker: "RELIANCE", name: "Reliance Industries" },
  { ticker: "SBIN", name: "State Bank of India" },
  { ticker: "SHRIRAMFIN", name: "Shriram Finance" },
  { ticker: "SUNPHARMA", name: "Sun Pharma" },
  { ticker: "TATACONSUM", name: "Tata Consumer Products" },
  { ticker: "TATAMOTORS", name: "Tata Motors" },
  { ticker: "TATASTEEL", name: "Tata Steel" },
  { ticker: "TCS", name: "Tata Consultancy Services" },
  { ticker: "TECHM", name: "Tech Mahindra" },
  { ticker: "TITAN", name: "Titan" },
  { ticker: "TRENT", name: "Trent" },
  { ticker: "ULTRACEMCO", name: "UltraTech Cement" },
  { ticker: "WIPRO", name: "Wipro" }
];

