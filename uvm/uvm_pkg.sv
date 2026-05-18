package uvm_pkg;
  parameter UVM_LOW=200, UVM_MEDIUM=300, UVM_HIGH=400;
  parameter UVM_FULL=500, UVM_DEBUG=600, UVM_NONE=700;
  parameter UVM_ACTIVE=1, UVM_PASSIVE=0;
  parameter UVM_NO_COVERAGE=0, UVM_CVR_ALL=1, UVM_DEFAULT=0;
  parameter UVM_CVR_REG_WIDTH=32;

  function void uvm_info(string id, string msg, int v);
    $display("[UVM_INFO] %s: %s", id, msg);
  endfunction
  function void uvm_warning(string id, string msg);
    $warning("[UVM_WARNING] %s: %s", id, msg);
  endfunction
  function void uvm_error(string id, string msg);
    $error("[UVM_ERROR] %s: %s", id, msg);
  endfunction
  function void uvm_fatal(string id, string msg);
    $fatal(1, "[UVM_FATAL] %s: %s", id, msg);
  endfunction

  class uvm_phase;
    function void raise_objection();
    endfunction
    function void drop_objection();
    endfunction
  endclass

  class uvm_object;
    string m_name;
    function new(string n);
      m_name = n;
    endfunction
    function string get_name();
      return m_name;
    endfunction
    function string get_type_name();
      return m_name;
    endfunction
  endclass

  class uvm_component extends uvm_object;
    uvm_component m_parent;
    function new(string n, uvm_component p);
      super.new(n);
      m_parent = p;
    endfunction
    function string get_full_name();
      if (m_parent == null) return m_name;
      return {m_parent.get_full_name(), ".", m_name};
    endfunction
    virtual function void build_phase(uvm_phase ph);
    endfunction
    virtual function void connect_phase(uvm_phase ph);
    endfunction
    virtual task run_phase(uvm_phase ph);
    endtask
    virtual function void report_phase(uvm_phase ph);
    endfunction
    virtual function void final_phase(uvm_phase ph);
    endfunction
  endclass

  class uvm_sequence_item extends uvm_object;
    function new(string n);
      super.new(n);
    endfunction
  endclass

  class uvm_sequencer extends uvm_component;
    function new(string n, uvm_component p);
      super.new(n, p);
    endfunction
  endclass

  class uvm_sequence extends uvm_sequence_item;
    uvm_sequencer m_sequencer;
    function new(string n);
      super.new(n);
    endfunction
    virtual task body();
    endtask
    task start(uvm_sequencer s);
      m_sequencer = s;
      body();
    endtask
    function void set_item_context(uvm_sequencer s);
      m_sequencer = s;
    endfunction
  endclass

  class uvm_driver extends uvm_component;
    uvm_sequence_item req;
    function new(string n, uvm_component p);
      super.new(n, p);
    endfunction
  endclass

  class uvm_monitor extends uvm_component;
    function new(string n, uvm_component p);
      super.new(n, p);
    endfunction
  endclass

  class uvm_agent extends uvm_component;
    function new(string n, uvm_component p);
      super.new(n, p);
    endfunction
    function bit get_is_active();
      return 1;
    endfunction
  endclass

  class uvm_scoreboard extends uvm_component;
    function new(string n, uvm_component p);
      super.new(n, p);
    endfunction
  endclass

  class uvm_subscriber extends uvm_component;
    function new(string n, uvm_component p);
      super.new(n, p);
    endfunction
  endclass

  class uvm_env extends uvm_component;
    function new(string n, uvm_component p);
      super.new(n, p);
    endfunction
  endclass

  class uvm_test extends uvm_component;
    function new(string n, uvm_component p);
      super.new(n, p);
    endfunction
  endclass

  class uvm_analysis_port extends uvm_component;
    function new(string n, uvm_component p);
      super.new(n, p);
    endfunction
    function void write(uvm_sequence_item t);
    endfunction
    function void connect(uvm_analysis_imp imp);
    endfunction
  endclass

  class uvm_analysis_imp extends uvm_component;
    function new(string n, uvm_component p);
      super.new(n, p);
    endfunction
    function void write(uvm_sequence_item t);
    endfunction
  endclass

  class uvm_config_db;
    static function bit get(uvm_component c, string i, string f, ref uvm_object v);
      return 0;
    endfunction
    static function void set(uvm_component c, string i, string f, uvm_object v);
    endfunction
    static function bit get_string(uvm_component c, string i, string f, ref string v);
      return 0;
    endfunction
    static function void set_string(uvm_component c, string i, string f, string v);
    endfunction
    static function void set_int(uvm_component c, string i, string f, int v);
    endfunction
    static function void set_virtual(uvm_component c, string i, string f, uvm_object v);
    endfunction
    static function bit get_virtual(uvm_component c, string i, string f, ref uvm_object v);
      return 0;
    endfunction
  endclass

  class uvm_reg_field extends uvm_object;
    function new(string n);
      super.new(n);
    endfunction
    function void configure(uvm_reg r, int sz, int lsb, string access, bit vol, int rst, bit has_cover, bit rmod, bit auto_eff);
    endfunction
    function string get_access();
      return "RW";
    endfunction
    function int get_n_bits();
      return 32;
    endfunction
    function int get();
      return 0;
    endfunction
    function void set(int v);
    endfunction
    function int get_reset();
      return 0;
    endfunction
  endclass

  class uvm_reg extends uvm_object;
    function new(string n);
      super.new(n);
    endfunction
    virtual function void build();
    endfunction
    function void configure(uvm_reg_block blk, uvm_reg_map m, int addr, string access, bit vol, uvm_reg_field f, int sz, int lsb, int r);
    endfunction
    function uvm_reg_field get_field_by_name(string n);
      return null;
    endfunction
    function void set_reset();
    endfunction
  endclass

  class uvm_reg_map extends uvm_object;
    function new(string n);
      super.new(n);
    endfunction
    function void add_reg(uvm_reg r, int offset, string access);
    endfunction
    function void set_auto_predict(bit v);
    endfunction
    function uvm_reg get_reg_by_offset(int offset);
      return null;
    endfunction
    function void set_base_addr(int a);
    endfunction
    function int get_base_addr();
      return 0;
    endfunction
  endclass

  class uvm_reg_block extends uvm_object;
    uvm_reg_map default_map;
    function new(string n);
      super.new(n);
    endfunction
    virtual function void build();
    endfunction
    function void default_map_set(uvm_reg_map m);
      default_map = m;
    endfunction
    function uvm_reg_map get_default_map();
      return default_map;
    endfunction
    function void lock_model();
    endfunction
    function void set_parent(uvm_reg_block p);
    endfunction
  endclass

  function void uvm_top_print_topology();
  endfunction
  function void run_test(string test_name);
    $display("UVM: run_test(%s) called", test_name);
  endfunction
endpackage
