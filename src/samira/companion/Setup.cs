using System;
using System.IO;
using System.Diagnostics;
using System.Drawing;
using System.Windows.Forms;
using System.Web.Script.Serialization;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Text;

class Setup : Form {
    TextBox game = new TextBox(), output = new TextBox();
    ComboBox repentogon = new ComboBox();
    ComboBox display = new ComboBox();
    string root = AppDomain.CurrentDomain.BaseDirectory, python, package;
    List<Button> actions = new List<Button>();
    bool zh = System.Globalization.CultureInfo.CurrentUICulture.TwoLetterISOLanguageName == "zh";
    bool previewMode;
    string T(string cn,string en) {return zh?cn:en;}
    string Q(string s) {
        // Windows argv quoting: double trailing backslashes before the closing
        // quote, and escape embedded quotes without changing the argument.
        var result=new StringBuilder("\"");int slashes=0;
        foreach(char c in s) {
            if(c=='\\'){slashes++;continue;}
            result.Append('\\',c=='"'?slashes*2+1:slashes);
            result.Append(c);slashes=0;
        }
        result.Append('\\',slashes*2);result.Append('"');return result.ToString();
    }
    string FailureHint(string message) {
        if(message.IndexOf("Update companion from this full package",StringComparison.OrdinalIgnoreCase)>=0)
            return T("请先用本次完整配套包点击“更新”，再使用显示方式切换功能。也可以选好显示方式后直接点击“更新”。","Click Update from this full package before using the mode switch. You can select the mode before clicking Update.");
        if(message.IndexOf("Close Isaac",StringComparison.OrdinalIgnoreCase)>=0)
            return T("检测到以撒进程仍在运行，请完全退出游戏后重试。","Isaac is still running. Exit the game completely and retry.");
        if(message.IndexOf("denied",StringComparison.OrdinalIgnoreCase)>=0 || message.Contains("拒绝访问"))
            return T("当前目录拒绝访问。请右键安装器，以管理员身份运行。","Access to this location was denied. Run Setup as administrator.");
        return T("请查看上方具体错误。确认配套 ZIP 已完整解压，路径正确；若仍失败，请将此错误反馈给作者。","See the specific error above. Check that the ZIP is fully extracted and paths are correct; report the error if it persists.");
    }
    Dictionary<string,object> Call(string action, string selectedGame = "", string selectedRepentogon = "", string selectedDisplay = "") {
        var start=new ProcessStartInfo(python,"-I -B "+Q(Path.Combine(root,"installer.py"))+" --action "+action+
            " --game "+Q(selectedGame)+" --repentogon "+Q(selectedRepentogon)+" --package "+Q(package));
        if(selectedDisplay.Length>0)start.Arguments+=" --presentation "+selectedDisplay;
        if(File.Exists(Path.Combine(root,"installation.json")))
            start.Arguments+=" --home "+Q(Directory.GetParent(root.TrimEnd(Path.DirectorySeparatorChar)).Parent.FullName);
        start.UseShellExecute=false; start.CreateNoWindow=true;start.RedirectStandardOutput=true;start.RedirectStandardError=true;
        using(var p=Process.Start(start)) {
            string text=p.StandardOutput.ReadToEnd();string err=p.StandardError.ReadToEnd();p.WaitForExit();
            if(text.Trim().Length==0) throw new Exception(err.Length>0?err:"No response from installer.");
            var data=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(text);
            if(data.ContainsKey("error"))throw new Exception(data["error"].ToString());return data;
        }
    }
    public Setup() {
        Text="Samira Companion"; ClientSize=new Size(780,540);StartPosition=FormStartPosition.CenterScreen;
        Font=new Font("Segoe UI",10);FormBorderStyle=FormBorderStyle.FixedDialog;MaximizeBox=false;
        package=root;python=Path.Combine(root,"payload","python","python.exe");
        var heading=new Label{Text=T("铁男配套程序 · 安装与维护","Samira companion · Setup and maintenance"),Location=new Point(18,16),AutoSize=true};Controls.Add(heading);
        Controls.Add(new Label{Text=T("以撒游戏目录（存放 mods 的那一层）","Isaac game folder (the folder containing mods)"),Location=new Point(18,52),AutoSize=true});
        game.SetBounds(18,80,645,28);Controls.Add(game);
        game.TextChanged+=(s,e)=>{repentogon.Items.Clear();repentogon.Text="";};
        var browse=new Button{Text=T("浏览…","Browse…"),Location=new Point(670,79),Size=new Size(90,30)};
        browse.Click+=(s,e)=>{using(var d=new FolderBrowserDialog()){if(d.ShowDialog()==DialogResult.OK)game.Text=d.SelectedPath;}};Controls.Add(browse);
        Controls.Add(new Label{Text=T("忏悔龙运行目录（包含 isaac-ng.exe 和 zhlLoader.dll，可在任意位置）","REPENTOGON runtime folder (isaac-ng.exe + zhlLoader.dll; any location)"),Location=new Point(18,119),AutoSize=true});
        repentogon.SetBounds(18,147,535,28);repentogon.DropDownStyle=ComboBoxStyle.DropDown;Controls.Add(repentogon);
        var find=new Button{Text=T("自动识别","Detect"),Location=new Point(560,146),Size=new Size(100,30)};
        find.Click+=async(s,e)=>await DetectPaths();actions.Add(find);Controls.Add(find);
        var browseRepentogon=new Button{Text=T("浏览…","Browse…"),Location=new Point(670,146),Size=new Size(90,30)};
        browseRepentogon.Click+=(s,e)=>{using(var d=new FolderBrowserDialog()){if(d.ShowDialog()==DialogResult.OK)repentogon.Text=d.SelectedPath;}};Controls.Add(browseRepentogon);
        Controls.Add(new Label{Text=T("显示方式","Display mode"),Location=new Point(18,201),AutoSize=true});
        display.SetBounds(125,196,420,30);display.DropDownStyle=ComboBoxStyle.DropDownList;
        display.Items.AddRange(new object[]{T("保持当前（新安装使用标准）","Keep current (new installs use Standard)"),
            T("标准模式","Standard"),T("黑屏兼容模式（模型正常、地图黑屏时选）","Black-screen compatibility (model visible, map black)")});
        display.SelectedIndex=0;Controls.Add(display);
        var saveDisplay=new Button{Text=T("应用显示方式","Apply display mode"),Location=new Point(560,195),Size=new Size(200,32)};
        saveDisplay.Click+=async(s,e)=>{
            if(game.Text.Trim().Length==0){MessageBox.Show(T("请选择游戏目录。","Select the game folder."));return;}
            if(display.SelectedIndex==0){MessageBox.Show(T("请先选择标准模式或黑屏兼容模式。","Select Standard or Black-screen compatibility first."));return;}
            string selectedGame=game.Text,selectedRepentogon=repentogon.Text,selectedDisplay=DisplayValue();
            foreach(var button in actions)button.Enabled=false;
            try{await Task.Run(()=>Call("display",selectedGame,selectedRepentogon,selectedDisplay));
                output.Text=T("显示方式已保存，下次启动游戏生效。无需重新安装。","Display mode saved for the next game launch. No reinstall needed.");}
            catch(Exception error){output.Text=error.Message+"\r\n\r\n"+FailureHint(error.Message);}
            finally{foreach(var button in actions)button.Enabled=true;}
        };actions.Add(saveDisplay);Controls.Add(saveDisplay);
        string[] names={T("安装","Install"),T("修复","Repair"),T("更新","Update"),T("回退版本","Roll back"),T("卸载","Uninstall")};
        string[] ops={"install","repair","update","rollback","uninstall"};
        for(int i=0;i<ops.Length;i++) {
            string action=ops[i];var b=new Button{Text=names[i],Location=new Point(18+i*150,250),Size=new Size(142,34)};
            b.Click+=async(s,e)=>{
                if(game.Text.Trim().Length==0){MessageBox.Show(T("请选择游戏目录。","Select the game folder."));return;}
                if(action=="uninstall" && MessageBox.Show(T("卸载配套程序？保留 Mod、存档和设置。","Uninstall companion? The mod, saves and settings are preserved."),Text,MessageBoxButtons.OKCancel)!=DialogResult.OK)return;
                foreach(var button in actions)button.Enabled=false;
                output.Text=T("正在处理，请稍候…","Working, please wait…");
                try {
                    // Capture UI values before entering the worker thread.
                    string selectedGame=game.Text, selectedRepentogon=repentogon.Text;
                    string selectedDisplay=(action=="install" || action=="update" || action=="repair")?DisplayValue():"";
                    var data=await Task.Run(()=>Call(action,selectedGame,selectedRepentogon,selectedDisplay));
                    if(data.ContainsKey("repentogon"))repentogon.Text=(string)data["repentogon"];
                    output.Text=T("操作成功。\r\n","Success.\r\n")+new JavaScriptSerializer().Serialize(data)+"\r\n\r\n"+
                        T("以后照常从忏悔龙启动器进入游戏。首次加载铁男时会自动启动渲染器。","Start the game through your usual REPENTOGON launcher. The renderer starts automatically for Samira.");
                }catch(Exception error){output.Text=error.Message+"\r\n\r\n"+FailureHint(error.Message);}
                foreach(var button in actions)button.Enabled=true;
            };actions.Add(b);Controls.Add(b);
        }
        output.Multiline=true;output.ReadOnly=true;output.ScrollBars=ScrollBars.Vertical;output.SetBounds(18,302,742,216);Controls.Add(output);
        Shown+=async(s,e)=>{if(previewMode)return;InitializeSetup();if(game.Text.Length==0)await DetectPaths();};
    }
    string DisplayValue(){return display.SelectedIndex==1?"glfw":display.SelectedIndex==2?"layered":"";}
    async Task DetectPaths() {
        foreach(var button in actions)button.Enabled=false;
        string selectedGame=game.Text;
        output.Text=T("正在查找游戏和忏悔龙目录…","Looking for Isaac and REPENTOGON folders…");
        try {
            var data=await Task.Run(()=>Call("discover",selectedGame));
            var games=(System.Collections.IEnumerable)data["games"];
            if(selectedGame.Trim().Length==0)foreach(var item in games){game.Text=(string)item;break;}
            repentogon.Items.Clear();repentogon.Text="";
            foreach(var item in (System.Collections.IEnumerable)data["repentogon"])repentogon.Items.Add((string)item);
            if(repentogon.Items.Count==1)repentogon.SelectedIndex=0;
            output.Text=repentogon.Items.Count==1
                ? T("已找到目录，请确认后安装。安装前请关闭游戏；以后照常使用忏悔龙启动器。","Folders found. Confirm them, close the game, then install. Keep using your usual REPENTOGON launcher.")
                : T("未找到唯一的忏悔龙目录。请从下拉列表选择、浏览或粘贴实际运行目录。不要选择只有启动器 EXE 的文件夹。","No unique REPENTOGON folder found. Choose a candidate, browse, or paste the runtime folder. A folder with only the launcher EXE is not enough.");
        }catch(Exception error){output.Text=error.Message+"\r\n"+FailureHint(error.Message);}
        finally{foreach(var button in actions)button.Enabled=true;}
    }
    void InitializeSetup() {
            try {
                if(!File.Exists(python)) {
                    var state=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(File.ReadAllText(Path.Combine(root,"installation.json")));
                    string current=state["current"] as string;
                    if(current==null)throw new Exception(T("配套程序已卸载。重新安装请使用完整配套包。","Companion is uninstalled. Use a complete package to reinstall."));
                    python=Path.Combine(root,current.Replace('/',Path.DirectorySeparatorChar),"python","python.exe");
                    game.Text=(string)state["game"];
                    repentogon.Text=state.ContainsKey("repentogon")?(string)state["repentogon"]:Path.Combine(game.Text,"Repentogon");
                    foreach(var obj in (System.Collections.IEnumerable)state["versions"]) {
                        var entry=(Dictionary<string,object>)obj;
                        if((string)entry["directory"]==current)package=(string)entry["package"];
                    }
                }
                output.Text=T("安装前请关闭游戏。更新会保留旧版本，支持回退；不修改游戏存档。\r\n更新方法：解压新配套包，运行其中的本工具，点击“更新”。\r\n本工具不联网下载更新，也不设置开机启动。","Close the game first. Updates keep the previous version for rollback and preserve saves.\r\nTo update, extract the new package and click Update in its setup tool.\r\nNo online downloads or Windows startup tasks are installed.");
            }catch(Exception error){output.Text=error.Message;foreach(var b in actions)b.Enabled=false;}
    }
    [STAThread]static void Main(string[] args){
        Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);
        if(args.Length==2 && (args[0]=="--preview" || args[0]=="--preview-en" || args[0]=="--preview-zh")){
            if(args[0]!="--preview")System.Threading.Thread.CurrentThread.CurrentUICulture=new System.Globalization.CultureInfo(args[0]=="--preview-en"?"en-US":"zh-CN");
            using(var f=new Setup()){
                f.previewMode=true;f.InitializeSetup();f.ShowInTaskbar=false;f.Opacity=0;f.Show();Application.DoEvents();
                using(var image=new Bitmap(f.Width,f.Height)){f.DrawToBitmap(image,new Rectangle(0,0,f.Width,f.Height));image.Save(args[1]);}
                File.WriteAllText(args[1]+".txt",f.output.Text);
            }
            return;
        }
        Application.Run(new Setup());
    }
}
